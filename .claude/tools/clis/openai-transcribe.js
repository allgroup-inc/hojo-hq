#!/usr/bin/env node
const API_KEY = process.env.OPENAI_API_KEY

if (!API_KEY) {
  console.error(JSON.stringify({ error: 'OPENAI_API_KEY environment variable required' }))
  process.exit(1)
}

const fs = require('fs')
const path = require('path')

function parseArgs(argv) {
  const out = { _: [] }
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    if (a.startsWith('--')) {
      const key = a.slice(2)
      const next = argv[i + 1]
      if (next !== undefined && !next.startsWith('--')) { out[key] = next; i++ }
      else out[key] = true
    } else {
      out._.push(a)
    }
  }
  return out
}

const args = parseArgs(process.argv.slice(2))
const cmd = args._[0]

async function transcribe(filePath, opts) {
  if (!fs.existsSync(filePath)) {
    return { error: `file not found: ${filePath}` }
  }
  const model = opts.model || 'whisper-1'
  const format = opts.format || 'verbose_json'
  if (opts['dry-run']) {
    return {
      _dry_run: true,
      method: 'POST',
      url: 'https://api.openai.com/v1/audio/transcriptions',
      headers: { Authorization: 'Bearer ***' },
      file: filePath,
      model,
      language: opts.language || undefined,
      prompt: opts.prompt || undefined,
      response_format: format,
    }
  }
  const buf = fs.readFileSync(filePath)
  const form = new FormData()
  form.append('file', new Blob([buf]), path.basename(filePath))
  form.append('model', model)
  form.append('response_format', format)
  if (opts.language) form.append('language', opts.language)
  if (opts.prompt) form.append('prompt', opts.prompt)

  const res = await fetch('https://api.openai.com/v1/audio/transcriptions', {
    method: 'POST',
    headers: { Authorization: `Bearer ${API_KEY}` },
    body: form,
  })
  const text = await res.text()
  try {
    return { status: res.status, ...JSON.parse(text) }
  } catch {
    return { status: res.status, raw: text }
  }
}

async function main() {
  if (cmd === 'transcribe') {
    const file = args._[1]
    if (!file) {
      console.error(JSON.stringify({
        error: '--file required',
        usage: 'openai-transcribe.js transcribe <audio-file> [--model whisper-1|gpt-4o-transcribe] [--language ja] [--prompt "context/spelling hints"] [--format verbose_json|text|srt|vtt] [--dry-run]',
      }))
      process.exit(1)
    }
    const result = await transcribe(file, args)
    console.log(JSON.stringify(result, null, 2))
  } else {
    console.error(JSON.stringify({
      error: 'Unknown command',
      usage: { transcribe: 'transcribe <audio-file> [--model] [--language] [--prompt] [--format] [--dry-run]' },
    }))
    process.exit(1)
  }
}

main()
