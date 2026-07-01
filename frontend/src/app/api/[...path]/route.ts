import { NextRequest } from "next/server";

const BASE = (process.env.AGENTOS_API_URL ?? "http://127.0.0.1:8000").replace(
  /\/$/,
  "",
);
const TOKEN = process.env.AGENTOS_API_TOKEN ?? "";

type Ctx = { params: Promise<{ path: string[] }> };

async function proxy(request: NextRequest, { params }: Ctx) {
  const { path } = await params;
  const search = new URL(request.url).search;
  const upstream = `${BASE}/${path.join("/")}${search}`;

  const headers: Record<string, string> = {};
  const ct = request.headers.get("content-type");
  if (ct) headers["Content-Type"] = ct;
  if (TOKEN) headers["Authorization"] = `Bearer ${TOKEN}`;

  const hasBody = !["GET", "HEAD", "DELETE"].includes(request.method);
  const body = hasBody ? await request.arrayBuffer() : undefined;

  const res = await fetch(upstream, {
    method: request.method,
    headers,
    body,
  });

  const text = await res.text();
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    data = { message: text };
  }

  return Response.json(data, { status: res.status });
}

export const GET = (req: NextRequest, ctx: Ctx) => proxy(req, ctx);
export const POST = (req: NextRequest, ctx: Ctx) => proxy(req, ctx);
export const PUT = (req: NextRequest, ctx: Ctx) => proxy(req, ctx);
export const PATCH = (req: NextRequest, ctx: Ctx) => proxy(req, ctx);
export const DELETE = (req: NextRequest, ctx: Ctx) => proxy(req, ctx);
