import json
import os
from typing import Dict, Any, List

def _escape_html(text: str) -> str:
    return (text or "").replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def _build_endpoint_form(endpoint: Dict[str, Any]) -> str:
    eid = endpoint['operationId']
    method = endpoint['method']
    path = endpoint['path']
    summary = _escape_html(endpoint.get('summary') or '')
    description = _escape_html(endpoint.get('description') or '')
    params: List[Dict[str, Any]] = endpoint.get('parameters', [])
    req_body = endpoint.get('requestBody')

    # Parameter inputs grouped by location
    param_inputs = []
    for p in params:
        pname = p.get('name')
        pin = p.get('in')
        required = p.get('required')
        schema = p.get('schema') or {}
        ptype = schema.get('type', 'string')
        enum = schema.get('enum')
        label = f"{pname} ({pin})" + (" *" if required else "")
        input_html = ''
        if enum:
            options = '\n'.join([f"<option value='{_escape_html(str(v))}'>{_escape_html(str(v))}</option>" for v in enum])
            input_html = f"<select name='{pname}' data-loc='{pin}' class='input'>{options}</select>"
        else:
            itype = 'number' if ptype in ['integer','number'] else 'text'
            input_html = f"<input type='{itype}' name='{pname}' data-loc='{pin}' class='input' {'required' if required else ''} />"
        param_inputs.append(f"<div class='field'><label>{label}</label>{input_html}</div>")

    # Request body (JSON only handled here)
    body_block = ''
    if isinstance(req_body, dict):
        content = req_body.get('content') or {}
        # pick application/json first
        json_ct = None
        for ct in content.keys():
            if 'json' in ct:
                json_ct = ct
                break
        if json_ct:
            body_block = f"""
            <div class='field'>
              <label>Request Body JSON{ ' *' if req_body.get('required') else ''}</label>
              <textarea name='__body' data-ct='{json_ct}' class='input body-input' placeholder='{{}}'></textarea>
            </div>
            """.strip()

    return f"""
    <details class='endpoint' id='ep-{eid}'>
      <summary><span class='method method-{method}'>{method}</span> <code>{_escape_html(path)}</code> <span class='ep-summary'>{summary}</span></summary>
      <form class='ep-form' data-method='{method}' data-path='{_escape_html(path)}' data-opid='{eid}'>
        <div class='ep-desc'>{description}</div>
        {''.join(param_inputs)}
        {body_block}
        <div class='actions'>
           <button type='submit' class='btn run-btn'>Send</button>
           <button type='button' class='btn curl-btn' data-copy='curl'>Copy cURL</button>
        </div>
        <div class='result hidden'>
            <div class='meta'></div>
            <pre class='resp-body'><code class='code-block'></code></pre>
        </div>
      </form>
    </details>
    """


def build_static_ui(api_summary: Dict[str, Any]) -> Dict[str, str]:
    """Return dict with index.html, script.js, styles.css content built deterministically from api_summary."""
    endpoints = api_summary.get('endpoints', [])
    # Group by tag
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for ep in endpoints:
        tags = ep.get('tags') or ['Default']
        for t in tags:
            groups.setdefault(t, []).append(ep)

    # Sort groups and endpoints for stability
    for g in groups.values():
        g.sort(key=lambda e: (e.get('path'), e.get('method')))
    sorted_group_items = sorted(groups.items(), key=lambda x: x[0].lower())

    nav_html = '\n'.join([f"<li><a href='#tag-{_escape_html(tag)}'>{_escape_html(tag)}</a></li>" for tag,_ in sorted_group_items])

    sections_html_parts = []
    for tag, eps in sorted_group_items:
        forms = '\n'.join([_build_endpoint_form(e) for e in eps])
        sections_html_parts.append(f"<section class='tag-group' id='tag-{_escape_html(tag)}'><h2>{_escape_html(tag)}</h2>{forms}</section>")
    sections_html = '\n'.join(sections_html_parts)

    first_server = ''
    servers = api_summary.get('servers') or []
    if servers:
        first = servers[0]
        if isinstance(first, dict):
            first_server = first.get('url','')
        elif isinstance(first, str):
            first_server = first

    info = api_summary.get('info', {})
    title = _escape_html(info.get('title','API'))
    version = _escape_html(info.get('version',''))

    index_html = f"""<!DOCTYPE html>
<html lang='en'>
<head>
<meta charset='utf-8'/>
<meta name='viewport' content='width=device-width, initial-scale=1'/>
<title>{title} – API Console</title>
<link rel='stylesheet' href='styles.css'/>
</head>
<body>
<header>
  <div class='branding'>
    <h1>{title}</h1>
    <span class='version'>v{version}</span>
  </div>
  <div class='auth-box'>
    <input type='text' id='base-url' placeholder='Base URL' value='{_escape_html(first_server)}' />
    <input type='text' id='auth-token' placeholder='Bearer Token (optional)' />
    <button id='save-env' class='btn'>Save</button>
  </div>
</header>
<aside class='sidebar'>
  <div class='search-box'><input type='text' id='search' placeholder='Search endpoints...'/></div>
  <nav><ul>{nav_html}</ul></nav>
</aside>
<main id='main'>
{sections_html}
</main>
<footer>Generated deterministically – no LLM artifacts.</footer>
<script src='script.js'></script>
</body>
</html>"""

    # script.js content
    script_js = f"""// Deterministic API console script
(function() {{
  const q = sel => document.querySelector(sel);
  const qa = sel => Array.from(document.querySelectorAll(sel));
  const storageKey = 'api_console_env_v1';
  function loadEnv() {{
    try {{ return JSON.parse(localStorage.getItem(storageKey)) || {{}}; }} catch(e) {{ return {{}}; }}
  }}
  function saveEnv(env) {{ localStorage.setItem(storageKey, JSON.stringify(env)); }}
  const env = loadEnv();
  if(env.baseUrl) q('#base-url').value = env.baseUrl;
  if(env.token) q('#auth-token').value = env.token;
  q('#save-env').addEventListener('click', () => {{
    saveEnv({{ baseUrl: q('#base-url').value.trim(), token: q('#auth-token').value.trim() }});
    alert('Environment saved');
  }});

  // Search filter
  q('#search').addEventListener('input', e => {{
    const term = e.target.value.toLowerCase();
    qa('.endpoint').forEach(d => {{
      const text = d.textContent.toLowerCase();
      d.style.display = text.includes(term) ? '' : 'none';
    }});
  }});

  function buildUrl(base, path, form) {{
    // Replace path params
    let url = path.replace(/\{{(.*?)\}}/g, (_, name) => {{
      const inp = form.querySelector(`[name="${{name}}"][data-loc="path"]`);
      return inp ? encodeURIComponent(inp.value || '') : '';
    }});
    // Query params
    const qp = [];
    form.querySelectorAll('[data-loc="query"]').forEach(inp => {{
      if(inp.value) qp.push(`${{encodeURIComponent(inp.name)}}=${{encodeURIComponent(inp.value)}}`);
    }});
    if(qp.length) url += (url.includes('?')?'&':'?') + qp.join('&');
    return base.replace(/\/$/, '') + url;
  }}

  function highlightJson(str) {{
    if(!str) return '';
    try {{
      const obj = typeof str === 'string' ? JSON.parse(str) : str;
      str = JSON.stringify(obj, null, 2);
    }} catch(e) {{}}
    return str.replace(/(&|<|>)/g, c => ({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c]))
      .replace(/("(\\u[a-zA-Z0-9]{{4}}|\\[^u]|[^\\"])*"(:)?|\b(true|false|null)\b|-?\b\d+(?:\.\d+)?\b)/g, m => {{
        let cls = 'num';
        if(/^"/.test(m)) {{ cls = /:$/.test(m) ? 'key' : 'str'; }}
        else if(/true|false/.test(m)) cls = 'bool';
        else if(/null/.test(m)) cls = 'null';
        return `<span class="${{cls}}">${{m}}</span>`;
      }});
  }}

  async function runEndpoint(form) {{
    const method = form.dataset.method;
    const path = form.dataset.path;
    const baseUrl = q('#base-url').value.trim();
    const token = q('#auth-token').value.trim();
    const url = buildUrl(baseUrl, path, form);
    const headers = {{ 'Accept': 'application/json' }};
    if(token) headers['Authorization'] = 'Bearer ' + token;
    let body = undefined;
    const bodyField = form.querySelector('textarea[name="__body"]');
    if(bodyField && bodyField.value.trim()) {{
      headers['Content-Type'] = 'application/json';
      body = bodyField.value.trim();
    }}
    const metaDiv = form.querySelector('.result .meta');
    const codeBlock = form.querySelector('.result code');
    form.querySelector('.result').classList.remove('hidden');
    metaDiv.textContent = 'Loading...';
    codeBlock.innerHTML = '';
    try {{
      const resp = await fetch(url, {{ method, headers, body }});
      const text = await resp.text();
      metaDiv.textContent = `${{resp.status}} ${{resp.statusText}}`;    
      codeBlock.innerHTML = highlightJson(text);
    }} catch(err) {{
      metaDiv.textContent = 'Error';
      codeBlock.textContent = err.message;
    }}
  }}

  qa('.ep-form').forEach(form => {{
    form.addEventListener('submit', e => {{ e.preventDefault(); runEndpoint(form); }});
    const curlBtn = form.querySelector('.curl-btn');
    if(curlBtn) curlBtn.addEventListener('click', () => {{
      const method = form.dataset.method;
      const path = form.dataset.path;
      const baseUrl = q('#base-url').value.trim();
      const token = q('#auth-token').value.trim();
      const built = buildUrl(baseUrl, path, form);
      const bodyField = form.querySelector('textarea[name="__body"]');
      let cmd = ['curl', '-X', method, `'${built}'`];
      if(token) cmd.push('-H', `'Authorization: Bearer ${token}'`);
      form.querySelectorAll('[data-loc="header"]').forEach(h => {{
        if(h.value) cmd.push('-H', `'${h.name}: ${h.value}'`);
      }});
      if(bodyField && bodyField.value.trim()) cmd.push('-H', `'Content-Type: application/json'`, '--data', `'${bodyField.value.replace("'","'\''")}'`);
      navigator.clipboard.writeText(cmd.join(' '));
      curlBtn.textContent = 'Copied!';
      setTimeout(()=>curlBtn.textContent='Copy cURL',1200);
    }});
  }});
}})();
"""

    styles_css = """*{box-sizing:border-box}body{margin:0;font-family:system-ui,Arial,sans-serif;color:#222;display:flex;min-height:100vh}header{position:fixed;top:0;left:0;right:0;background:#1f2937;color:#fff;display:flex;justify-content:space-between;align-items:center;padding:8px 16px;z-index:10}header .branding h1{margin:0;font-size:18px}.version{background:#374151;padding:2px 6px;border-radius:4px;font-size:12px;margin-left:6px}.auth-box{display:flex;gap:6px}input,textarea,select{font:inherit;padding:6px;border:1px solid #ccc;border-radius:4px;width:100%}.sidebar{position:fixed;top:56px;left:0;bottom:0;width:220px;background:#f3f4f6;border-right:1px solid #e5e7eb;overflow:auto;padding:8px}main{margin-top:56px;margin-left:220px;padding:16px;flex:1;overflow:auto}nav ul{list-style:none;padding:0;margin:0}nav li{margin:4px 0}nav a{text-decoration:none;color:#111;padding:4px 6px;display:block;border-radius:4px}nav a:hover{background:#e5e7eb}.search-box input{width:100%;margin-bottom:8px}.tag-group{margin-bottom:32px}.tag-group h2{border-bottom:2px solid #ddd;padding-bottom:4px}.endpoint{border:1px solid #d1d5db;border-radius:6px;margin:8px 0;background:#fff}details[open]{box-shadow:0 2px 4px rgba(0,0,0,.08)}.endpoint summary{cursor:pointer;padding:6px 10px;display:flex;align-items:center;gap:8px;background:#f9fafb}.endpoint form{padding:10px;display:flex;flex-direction:column;gap:10px}.method{font-size:11px;font-weight:600;padding:2px 6px;border-radius:4px;color:#fff;text-transform:uppercase}.method-GET{background:#2563eb}.method-POST{background:#059669}.method-PUT{background:#d97706}.method-DELETE{background:#dc2626}.field{display:flex;flex-direction:column;gap:4px}.actions{display:flex;gap:8px}.btn{background:#2563eb;color:#fff;border:none;padding:6px 12px;border-radius:4px;cursor:pointer;font-size:14px}.btn:hover{background:#1d4ed8}.run-btn{background:#059669}.run-btn:hover{background:#047857}.result{border-top:1px solid #eee;padding:6px 0}.hidden{display:none}.resp-body{background:#111;color:#f1f5f9;padding:10px;border-radius:6px;overflow:auto;max-height:380px}.resp-body code{font-family:ui-monospace,monospace;font-size:12px;line-height:1.4}.code-block .key{color:#93c5fd}.code-block .str{color:#86efac}.code-block .num{color:#fcd34d}.code-block .bool{color:#fca5a5}.code-block .null{color:#cbd5e1}.ep-desc{font-size:13px;color:#555}.body-input{min-height:120px;font-family:ui-monospace,monospace}.footer{margin-top:40px;font-size:12px;color:#666}@media (max-width:860px){.sidebar{position:static;width:auto;height:auto;display:block;border-right:none}main{margin-left:0}header{flex-wrap:wrap;gap:8px}}
"""

    return {
        'index.html': index_html,
        'script.js': script_js,
        'styles.css': styles_css,
        'api-summary.json': json.dumps(api_summary, indent=2)
    }


def write_static_ui(api_summary: Dict[str, Any], output_dir: str = 'ui') -> Dict[str, str]:
    os.makedirs(output_dir, exist_ok=True)
    assets = build_static_ui(api_summary)
    paths = {}
    for name, content in assets.items():
        path = os.path.join(output_dir, name)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        paths[name] = path
    return paths
