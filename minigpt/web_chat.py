"""Serveur localhost pour la génération réelle du mini-GPT, sans service externe."""
import argparse
import hashlib
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import torch
from minigpt.bpe import BPETokenizer
from minigpt.finetune import restore_model
from minigpt.conversation import reply


def main():
    """Charge une seule fois les poids et sert la page et son point de génération."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--tokenizer', type=Path, required=True)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    torch.set_num_threads(4)
    saved = torch.load(args.checkpoint, map_location='cpu', weights_only=True)
    model = restore_model(saved)
    tokenizer = BPETokenizer.load(args.tokenizer)
    # Un tokenizer de même taille peut avoir des merges différents.
    metadata = saved.get('chat_sft', saved.get('interpolation', {}))
    expected_hash = metadata.get('tokenizer_sha256')
    if len(tokenizer.vocab) != model.cfg.vocab_size or (
        expected_hash and hashlib.sha256(args.tokenizer.read_bytes()).hexdigest() != expected_hash
    ):
        parser.error('Tokenizer incompatible avec le checkpoint.')
    lock = threading.Lock()
    page = (Path(__file__).resolve().parents[1] / 'demo/index.html').read_bytes()

    class Handler(BaseHTTPRequestHandler):
        """Expose une API bornée et empêche les accès croisés depuis une autre origine."""
        def respond(self, code, content, kind='application/json; charset=utf-8'):
            """Écrit une réponse de taille connue, sans cache des conversations."""
            raw = content if isinstance(content, bytes) else json.dumps(content, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(raw)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            """Sert uniquement la page et le nom des poids chargés."""
            if self.path == '/':
                self.respond(200, page, 'text/html; charset=utf-8')
            elif self.path == '/api/info':
                self.respond(200, {'checkpoint': args.checkpoint.name})
            else:
                self.respond(404, {'error': 'Page inconnue'})

        def do_POST(self):
            """Valide les rôles et appelle exclusivement le modèle local."""
            if self.path != '/api/chat':
                return self.respond(404, {'error': 'Route inconnue'})
            origin = self.headers.get('Origin')
            if origin and origin not in [f'http://localhost:{args.port}', f'http://127.0.0.1:{args.port}']:
                return self.respond(403, {'error': 'Origine refusée'})
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 100000:
                    raise ValueError('Discussion trop longue')
                history = json.loads(self.rfile.read(length))['history']
                if not isinstance(history, list) or not 1 <= len(history) <= 101 or len(history) % 2 != 1:
                    raise ValueError('Historique invalide')
                for index, turn in enumerate(history):
                    # L’alternance et la taille sont vérifiées avant de passer au modèle.
                    role = 'user' if index % 2 == 0 else 'assistant'
                    if (not isinstance(turn, list) or len(turn) != 2 or turn[0] != role
                            or not isinstance(turn[1], str) or len(turn[1]) > 2000):
                        raise ValueError('Tour invalide')
                with lock:
                    result = reply(model, tokenizer, history)
                self.respond(200, result)
            except (ValueError, KeyError, TypeError) as error:
                self.respond(400, {'error': str(error)})

    print(f'http://localhost:{args.port} — {args.checkpoint}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
