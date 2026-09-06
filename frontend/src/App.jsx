import { useEffect, useMemo, useState } from 'react'

const api = async (path, options = {}) => {
  const token = localStorage.getItem('storserver_token')
  const headers = { ...(options.headers || {}) }
  if (token) headers.Authorization = `Bearer ${token}`
  if (options.body && !(options.body instanceof FormData)) headers['Content-Type'] = 'application/json'
  const response = await fetch(path, { ...options, headers })
  const data = response.headers.get('content-type')?.includes('application/json') ? await response.json() : null
  if (!response.ok) throw new Error(data?.detail || `HTTP ${response.status}`)
  return data
}

function Login({ onLogin }) {
  const [email, setEmail] = useState('admin@hoststorm.cloud')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit(event) {
    event.preventDefault()
    setLoading(true)
    setError('')
    try {
      const body = new URLSearchParams({ username: email, password })
      const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
        body,
      })
      const data = await response.json()
      if (!response.ok) throw new Error(data.detail || 'Falha no login')
      localStorage.setItem('storserver_token', data.access_token)
      onLogin()
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="login-shell">
      <section className="login-card">
        <div className="brand-mark">S</div>
        <p className="eyebrow">HOSTSTORM CLOUD</p>
        <h1>StorServer</h1>
        <p className="muted">Game hosting control plane</p>
        <form onSubmit={submit}>
          <label>E-mail<input value={email} onChange={e => setEmail(e.target.value)} type="email" required /></label>
          <label>Senha<input value={password} onChange={e => setPassword(e.target.value)} type="password" required /></label>
          {error && <div className="error">{error}</div>}
          <button disabled={loading}>{loading ? 'Entrando…' : 'Entrar'}</button>
        </form>
      </section>
    </main>
  )
}

function Dashboard({ onLogout }) {
  const [me, setMe] = useState(null)
  const [servers, setServers] = useState([])
  const [nodes, setNodes] = useState([])
  const [nodeStatus, setNodeStatus] = useState([])
  const [error, setError] = useState('')
  const [creating, setCreating] = useState(false)
  const [logs, setLogs] = useState(null)
  const [logsLoading, setLogsLoading] = useState(false)
  const [form, setForm] = useState({ name: '', game_key: 'cs16', node_id: '', cpu_limit: 2, memory_mb: 2048 })

  const running = useMemo(() => servers.filter(s => s.status === 'running').length, [servers])
  const onlineNodes = useMemo(() => nodeStatus.filter(n => n.online).length, [nodeStatus])

  async function refreshNodeStatus() {
    try {
      setNodeStatus(await api('/api/nodes/status'))
    } catch (err) {
      if (String(err.message).includes('401')) onLogout()
    }
  }

  async function refresh() {
    try {
      const [meData, serverData, nodeData, statusData] = await Promise.all([
        api('/api/me'), api('/api/servers'), api('/api/nodes'), api('/api/nodes/status')
      ])
      setMe(meData)
      setServers(serverData)
      setNodes(nodeData)
      setNodeStatus(statusData)
      if (!form.node_id && nodeData.length) setForm(current => ({ ...current, node_id: String(nodeData[0].id) }))
      setError('')
    } catch (err) {
      if (String(err.message).includes('401')) onLogout()
      else setError(err.message)
    }
  }

  useEffect(() => {
    refresh()
    const timer = window.setInterval(refreshNodeStatus, 10000)
    return () => window.clearInterval(timer)
  }, [])

  async function createServer(event) {
    event.preventDefault()
    setCreating(true)
    setError('')
    try {
      await api('/api/servers', {
        method: 'POST',
        body: JSON.stringify({
          ...form,
          node_id: Number(form.node_id),
          cpu_limit: Number(form.cpu_limit),
          memory_mb: Number(form.memory_mb),
        }),
      })
      setForm(current => ({ ...current, name: '' }))
      await refresh()
    } catch (err) {
      setError(err.message)
    } finally {
      setCreating(false)
    }
  }

  async function action(server, name) {
    setError('')
    try {
      await api(`/api/servers/${server.id}/${name}`, { method: 'POST' })
      await refresh()
    } catch (err) {
      setError(err.message)
    }
  }

  async function showLogs(server) {
    setLogsLoading(true)
    setError('')
    try {
      const data = await api(`/api/servers/${server.id}/logs?tail=400`)
      setLogs({ server, text: data.logs || '(sem logs)' })
    } catch (err) {
      setError(err.message)
    } finally {
      setLogsLoading(false)
    }
  }

  async function deleteServer(server) {
    if (!window.confirm(`Excluir o servidor "${server.name}"? O container será removido do node.`)) return
    setError('')
    try {
      await api(`/api/servers/${server.id}`, { method: 'DELETE' })
      if (logs?.server.id === server.id) setLogs(null)
      await refresh()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark small">S</span><div><strong>StorServer</strong><small>HOSTSTORM</small></div></div>
        <nav>
          <a className="active">Visão geral</a>
          <a>Servidores</a>
          <a>Nodes</a>
          <a>Backups</a>
          {me?.role === 'admin' && <a>Administração</a>}
        </nav>
        <div className="sidebar-foot">
          <span>{me?.email}</span>
          <button className="ghost" onClick={onLogout}>Sair</button>
        </div>
      </aside>

      <main className="content">
        <header><div><p className="eyebrow">CONTROL PLANE</p><h1>Visão geral</h1></div><span className="badge">{me?.role || '...'}</span></header>
        {error && <div className="error banner">{error}</div>}

        <section className="stats">
          <article><span>Servidores</span><strong>{servers.length}</strong></article>
          <article><span>Online</span><strong>{running}</strong></article>
          <article><span>Nodes online</span><strong>{onlineNodes}/{nodes.length}</strong></article>
          <article><span>Plataforma</span><strong>v0.1</strong></article>
        </section>

        <section className="grid-two">
          <article className="panel">
            <div className="panel-title"><div><p className="eyebrow">INVENTÁRIO</p><h2>Meus servidores</h2></div><button className="ghost" onClick={refresh}>Atualizar</button></div>
            <div className="server-list">
              {!servers.length && <p className="empty">Nenhum servidor criado ainda.</p>}
              {servers.map(server => (
                <div className="server-row" key={server.id}>
                  <div><strong>{server.name}</strong><small>{server.game_key} · node #{server.node_id}{server.public_port ? ` · ${server.public_host}:${server.public_port}` : ''}</small></div>
                  <span className={`status ${server.status}`}>{server.status}</span>
                  <div className="actions">
                    <button className="ghost" onClick={() => action(server, 'start')}>Start</button>
                    <button className="ghost" onClick={() => action(server, 'stop')}>Stop</button>
                    <button className="ghost" onClick={() => action(server, 'restart')}>Restart</button>
                    <button className="ghost" disabled={logsLoading} onClick={() => showLogs(server)}>Logs</button>
                    <button className="ghost danger" onClick={() => deleteServer(server)}>Excluir</button>
                  </div>
                </div>
              ))}
            </div>
          </article>

          <article className="panel">
            <p className="eyebrow">PROVISIONAMENTO</p><h2>Criar servidor</h2>
            <form className="create-form" onSubmit={createServer}>
              <label>Nome<input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="CS STORM" required /></label>
              <label>Jogo<select value={form.game_key} onChange={e => setForm({ ...form, game_key: e.target.value })}><option value="cs16">Counter-Strike 1.6</option><option value="kf2">Killing Floor 2</option><option value="ets2">Euro Truck Simulator 2</option><option value="ats">American Truck Simulator</option></select></label>
              <label>Node<select value={form.node_id} onChange={e => setForm({ ...form, node_id: e.target.value })} required>{nodes.map(node => <option key={node.id} value={node.id}>{node.name} ({node.region})</option>)}</select></label>
              <div className="form-row"><label>vCPU<input type="number" min="1" value={form.cpu_limit} onChange={e => setForm({ ...form, cpu_limit: e.target.value })} /></label><label>RAM MB<input type="number" min="512" step="512" value={form.memory_mb} onChange={e => setForm({ ...form, memory_mb: e.target.value })} /></label></div>
              <button disabled={creating || !nodes.length}>{creating ? 'Criando…' : 'Criar servidor'}</button>
            </form>
          </article>
        </section>

        <section className="panel node-panel">
          <div className="panel-title"><div><p className="eyebrow">INFRAESTRUTURA</p><h2>Saúde dos nodes</h2></div><button className="ghost" onClick={refreshNodeStatus}>Verificar agora</button></div>
          <div className="node-grid">
            {nodeStatus.map(node => (
              <article className="node-card" key={node.id}>
                <div><strong>{node.name}</strong><small>{node.region} · {node.hostname || 'hostname indisponível'}</small></div>
                <span className={`status ${node.online ? 'running' : 'error'}`}>{node.online ? 'online' : 'offline'}</span>
                {node.online ? <small>Docker {node.docker_version || '?'} · {node.containers_running ?? 0}/{node.containers ?? 0} containers · {node.cpus ?? '?'} CPU</small> : <small>{node.detail || 'Agent indisponível'}</small>}
              </article>
            ))}
          </div>
        </section>

        {logs && (
          <section className="panel logs-panel">
            <div className="panel-title"><div><p className="eyebrow">CONSOLE</p><h2>Logs · {logs.server.name}</h2></div><div className="actions"><button className="ghost" onClick={() => showLogs(logs.server)}>Atualizar</button><button className="ghost" onClick={() => setLogs(null)}>Fechar</button></div></div>
            <pre>{logs.text}</pre>
          </section>
        )}
      </main>
    </div>
  )
}

export default function App() {
  const [authenticated, setAuthenticated] = useState(Boolean(localStorage.getItem('storserver_token')))
  const logout = () => { localStorage.removeItem('storserver_token'); setAuthenticated(false) }
  return authenticated ? <Dashboard onLogout={logout} /> : <Login onLogin={() => setAuthenticated(true)} />
}
