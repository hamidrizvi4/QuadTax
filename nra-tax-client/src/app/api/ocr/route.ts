import { NextRequest, NextResponse } from 'next/server';

// Server-side proxy for the tax engine's /ocr endpoint.
//
// The engine API key lives ONLY here (server-side env), never in the browser
// bundle. The client posts multipart form data to this same-origin route; we
// forward it to the engine with the Bearer key attached. The raw FormData is
// forwarded as-is (fetch sets the multipart boundary automatically).

const ENGINE_URL =
  process.env.QUADTAX_ENGINE_URL ?? 'http://localhost:8000/api/v1';
const API_KEY = process.env.QUADTAX_API_KEY;

export async function POST(req: NextRequest) {
  if (!API_KEY) {
    return NextResponse.json(
      { detail: 'Server auth not configured' },
      { status: 503 },
    );
  }

  const form = await req.formData();

  const upstream = await fetch(`${ENGINE_URL}/ocr`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${API_KEY}`,
    },
    body: form,
  });

  const data = await upstream.json();
  return NextResponse.json(data, { status: upstream.status });
}
