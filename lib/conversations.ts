import { randomUUID } from "node:crypto";
import { promises as fs } from "node:fs";
import path from "node:path";

export type ConversationMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: string;
  meta?: Record<string, unknown>;
};

export type Conversation = {
  id: string;
  title: string;
  createdAt: string;
  updatedAt: string;
  messages: ConversationMessage[];
};

const STORE_PATH = path.join(process.cwd(), "tmp", "conversations.json");

async function ensureStore() {
  await fs.mkdir(path.dirname(STORE_PATH), { recursive: true });
  try {
    await fs.access(STORE_PATH);
  } catch {
    await fs.writeFile(STORE_PATH, JSON.stringify({ conversations: [] }, null, 2), "utf8");
  }
}

async function readStore(): Promise<{ conversations: Conversation[] }> {
  await ensureStore();
  try {
    const data = JSON.parse(await fs.readFile(STORE_PATH, "utf8")) as { conversations?: Conversation[] };
    return { conversations: Array.isArray(data.conversations) ? data.conversations : [] };
  } catch {
    return { conversations: [] };
  }
}

async function writeStore(store: { conversations: Conversation[] }) {
  await ensureStore();
  await fs.writeFile(STORE_PATH, JSON.stringify(store, null, 2) + "\n", "utf8");
}

function now() {
  return new Date().toISOString();
}

function titleFrom(content: string) {
  const value = content.replace(/\s+/g, " ").trim();
  return value ? value.slice(0, 24) : "新对话";
}

export async function listConversations() {
  const store = await readStore();
  return store.conversations
    .map(({ messages, ...item }) => ({ ...item, messageCount: messages.length }))
    .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export async function getConversation(id: string) {
  const store = await readStore();
  return store.conversations.find(item => item.id === id) || null;
}

export async function createConversation(title = "新对话") {
  const store = await readStore();
  const timestamp = now();
  const conversation: Conversation = {
    id: randomUUID(),
    title,
    createdAt: timestamp,
    updatedAt: timestamp,
    messages: []
  };
  store.conversations.unshift(conversation);
  await writeStore(store);
  return conversation;
}

export async function appendMessages(conversationId: string | undefined, messages: Omit<ConversationMessage, "id" | "createdAt">[]) {
  const store = await readStore();
  let conversation = conversationId ? store.conversations.find(item => item.id === conversationId) : undefined;
  if (!conversation) {
    conversation = {
      id: randomUUID(),
      title: titleFrom(messages.find(item => item.role === "user")?.content || ""),
      createdAt: now(),
      updatedAt: now(),
      messages: []
    };
    store.conversations.unshift(conversation);
  }
  const timestamp = now();
  for (const message of messages) {
    conversation.messages.push({ ...message, id: randomUUID(), createdAt: timestamp });
  }
  const firstUser = conversation.messages.find(item => item.role === "user");
  if (firstUser && conversation.title === "新对话") conversation.title = titleFrom(firstUser.content);
  conversation.updatedAt = timestamp;
  await writeStore(store);
  return conversation;
}

export async function deleteConversation(id: string) {
  const store = await readStore();
  const before = store.conversations.length;
  store.conversations = store.conversations.filter(item => item.id !== id);
  await writeStore(store);
  return before !== store.conversations.length;
}
