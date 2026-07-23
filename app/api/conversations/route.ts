import { NextRequest, NextResponse } from "next/server";
import { appendMessages, createConversation, deleteConversation, getConversation, listConversations } from "@/lib/conversations";

export const runtime = "nodejs";

export async function GET(request: NextRequest) {
  const id = request.nextUrl.searchParams.get("id");
  if (id) return NextResponse.json({ ok: true, conversation: await getConversation(id) });
  return NextResponse.json({ ok: true, conversations: await listConversations() });
}

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}));
  const action = String(body.action || "");
  if (action === "create") {
    const conversation = await createConversation(String(body.title || "新对话"));
    return NextResponse.json({ ok: true, conversation });
  }
  if (action === "append") {
    const conversation = await appendMessages(String(body.conversationId || ""), Array.isArray(body.messages) ? body.messages : []);
    return NextResponse.json({ ok: true, conversation });
  }
  if (action === "delete") {
    return NextResponse.json({ ok: true, deleted: await deleteConversation(String(body.conversationId || "")) });
  }
  return NextResponse.json({ ok: false, message: "不支持的会话操作。" }, { status: 400 });
}
