export function parsePort(value) {
  if (!/^\d+$/.test(String(value))) {
    throw new Error('E2E_API_PORT must be a valid TCP port')
  }

  const port = Number(value)
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error('E2E_API_PORT must be a valid TCP port')
  }
  return port
}

export function shellQuote(value) {
  return `'${String(value).replaceAll("'", `'"'"'`)}'`
}
