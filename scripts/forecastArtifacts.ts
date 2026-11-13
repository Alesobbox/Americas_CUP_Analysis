import { readFile } from 'node:fs/promises'
import path from 'node:path'
import type { Plugin } from 'vite'
import type { IncomingMessage, ServerResponse } from 'node:http'
import { createScenarioMiddleware } from './forecastScenarios.ts'
import { createKinematicMiddleware } from './kinematicScenarioMiddleware.ts'

const generatedDirectories = ['predictions', 'environment']

/** Serve generated JSON independently of Vite's watcher-maintained public inventory. */
function artifactMiddleware(publicDir: string, reportError: (message: string) => void) {
      const directories = generatedDirectories.map((name) => ({
        prefix: `/data/${name}`,
        root: path.resolve(publicDir, 'data', name),
      }))
      return (request: IncomingMessage, response: ServerResponse, next: () => void) => {
        const pathname = (request.url ?? '').split(/[?#]/, 1)[0]
        const inventory = pathname === '/data/artifacts.json'
        const directory = inventory ? { prefix: pathname, root: path.resolve(publicDir, 'data') } : directories.find(({ prefix }) => pathname === prefix || pathname.startsWith(`${prefix}/`))
        if (!directory) return next()

        const reply = (status: number, body: Buffer | string, contentType = 'application/json; charset=utf-8') => {
          const bytes = typeof body === 'string' ? Buffer.from(body) : body
          response.writeHead(status, {
            'Content-Type': contentType,
            'Content-Length': bytes.length,
            'Cache-Control': 'no-store',
            'X-Content-Type-Options': 'nosniff',
            ...(status === 405 ? { Allow: 'GET, HEAD' } : {}),
          })
          response.end(request.method === 'HEAD' ? undefined : bytes)
        }

        if (request.method !== 'GET' && request.method !== 'HEAD') {
          reply(405, '{"error":"Method not allowed"}\n')
          return
        }

        let relative: string
        try {
          relative = inventory ? 'artifacts.json' : decodeURIComponent(pathname.slice(directory.prefix.length + 1))
        } catch {
          reply(400, '{"error":"Invalid generated artifact path"}\n')
          return
        }
        // Only exported JSON/Markdown names are accepted; reject traversal and Windows separators.
        if (!/^(?:[a-zA-Z0-9_-]+\/)*[a-zA-Z0-9_-]+\.(?:json|md)$/.test(relative)) {
          reply(400, '{"error":"Invalid generated artifact path"}\n')
          return
        }

        // readFile closes its handle before replying. No watch handle can block
        // the publisher's atomic index replacement on Windows.
        const contentType = relative.endsWith('.md') ? 'text/markdown; charset=utf-8' : 'application/json; charset=utf-8'
        void readFile(path.join(directory.root, relative)).then(
          (bytes) => reply(200, bytes, contentType),
          (error: NodeJS.ErrnoException) => {
            const missing = error.code === 'ENOENT' || error.code === 'ENOTDIR'
            if (!missing) reportError(`Cannot read generated artifact: ${error.message}`)
            reply(missing ? 404 : 500, missing
              ? '{"error":"Generated artifact not found"}\n'
              : '{"error":"Cannot read generated artifact"}\n')
          },
        )
      }
}

export function forecastArtifactsPlugin(): Plugin {
  return {
    name: 'forecast-artifacts',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use(createScenarioMiddleware(server.config.root))
      server.middlewares.use(createKinematicMiddleware(server.config.root))
      server.middlewares.use(artifactMiddleware(server.config.publicDir, (message) => server.config.logger.error(message)))
    },
    configurePreviewServer(server) {
      server.middlewares.use(createScenarioMiddleware(server.config.root))
      server.middlewares.use(createKinematicMiddleware(server.config.root))
      server.middlewares.use(artifactMiddleware(server.config.publicDir, (message) => server.config.logger.error(message)))
    },
  }
}
