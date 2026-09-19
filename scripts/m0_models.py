"""Probe authorized OpenAI-compatible endpoints using synthetic input only.

Load repository .env; existing process environment values take precedence.
Print model identifiers and embedding dimensions, never API keys or raw responses.
"""
import json
import os
import sys
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
import urllib.error
import urllib.request

def call(prefix, route, payload):
    base = os.environ.get(prefix + '_BASE_URL', '').rstrip('/')
    model = os.environ.get(prefix + ('_NAME' if prefix == 'RELEX_MODEL' else '_MODEL'), '')
    if not base or not model:
        raise RuntimeError(prefix + ': base URL and model identifier must be configured')
    headers = {'Content-Type': 'application/json'}
    key = os.environ.get(prefix + '_API_KEY') or os.environ.get('OPENAI_API_KEY')
    if urlparse(base).hostname == 'api.openai.com' and not key:
        raise RuntimeError(prefix + ': OPENAI_API_KEY is missing; add it to the private repository .env')
    if key:
        headers['Authorization'] = 'Bearer ' + key
    request = urllib.request.Request(base + route, data=json.dumps(dict(payload, model=model)).encode(), headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return model, json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(prefix + ': HTTP ' + str(exc.code)) from None
    except urllib.error.URLError:
        raise RuntimeError(prefix + ': connection failed') from None

def main():
    model, result = call('RELEX_MODEL', '/chat/completions', {
        'messages': [{'role': 'user', 'content': 'Call the receipt_probe tool with record_id synthetic-1.'}],
        'tools': [{'type': 'function', 'function': {'name': 'receipt_probe', 'description': 'Synthetic feasibility tool', 'parameters': {'type': 'object', 'properties': {'record_id': {'type': 'string'}}, 'required': ['record_id']}}}],
        'tool_choice': {'type': 'function', 'function': {'name': 'receipt_probe'}}
    })
    calls = result['choices'][0]['message'].get('tool_calls', [])
    if not any(c['function']['name'] == 'receipt_probe' and json.loads(c['function']['arguments']).get('record_id') == 'synthetic-1' for c in calls):
        raise RuntimeError('Generation endpoint did not return the required real tool call')
    print(json.dumps({'generation_model': model, 'real_tool_call': True}))
    model, result = call('RELEX_EMBEDDING', '/embeddings', {'input': ['Synthetic project launch agreement.']})
    vector = result['data'][0]['embedding']
    if not vector or not all(isinstance(x, (int, float)) for x in vector):
        raise RuntimeError('Embedding endpoint did not return a numeric vector')
    print(json.dumps({'embedding_model': model, 'dimensions': len(vector)}))

if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, KeyError, ValueError, IndexError) as exc:
        print('M0 model probe failed: ' + str(exc), file=sys.stderr)
        sys.exit(1)
