"""client.py — Client RPC avec timeout et retries (Séance 4)."""
import urllib.request
import urllib.error
import json
import time
import uuid
import socket


class RpcClient:
    """Client RPC avec timeout, retries et backoff exponentiel."""

    def __init__(self, url: str, default_timeout: float = 5.0,
                 max_retries: int = 3, backoff_base: float = 1.0):
        self.url           = url
        self.default_timeout = default_timeout
        self.max_retries   = max_retries
        self.backoff_base  = backoff_base
        self.call_log: list[dict] = []

    def call(self, method: str, params: dict = None,
             timeout: float = None) -> dict:
        """Appel RPC avec retry automatique.

        Stratégie de retry :
          ✅ Timeout, erreur de connexion → retry
          ✅ Erreur interne serveur (-32603) → retry
          ❌ Erreur client (-32700, -32600, -32601, -32602) → pas de retry
          ❌ Erreur applicative (code > 0) → pas de retry

        Returns:
            Réponse RPC (dict avec result ou error).

        Raises:
            ConnectionError: si toutes les tentatives échouent.
        """
        rpc_id  = str(uuid.uuid4())
        timeout = timeout or self.default_timeout
        params  = params or {}

        call_entry = {
            "rpc_id":     rpc_id,
            "method":     method,
            "attempts":   0,
            "success":    False,
            "start_time": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            call_entry["attempts"] = attempt
            start = time.monotonic()

            try:
                body = json.dumps({
                    "rpc_version": "1.0",
                    "id":          rpc_id,
                    "method":      method,
                    "params":      params,
                    "sent_at":     time.strftime("%Y-%m-%dT%H:%M:%S"),
                }).encode("utf-8")

                req = urllib.request.Request(
                    self.url, data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    response = json.loads(resp.read().decode("utf-8"))

                duration = (time.monotonic() - start) * 1000
                call_entry["duration_ms"] = round(duration, 2)

                # Vérifier si l'erreur est retriable
                if response.get("error"):
                    code = response["error"].get("code", 0)
                    if code != -32603:
                        # Erreur client ou applicative → pas de retry
                        call_entry["success"] = False
                        self.call_log.append(call_entry)
                        return response

                call_entry["success"] = True
                self.call_log.append(call_entry)
                return response

            except (urllib.error.URLError, socket.timeout,
                    ConnectionRefusedError, ConnectionResetError) as e:
                last_error = e
                if attempt < self.max_retries:
                    delay = self.backoff_base * (2 ** (attempt - 1))
                    print(f"  ⚠ Tentative {attempt}/{self.max_retries} échouée "
                          f"({type(e).__name__}), retry dans {delay:.1f}s…")
                    time.sleep(delay)

        call_entry["success"] = False
        self.call_log.append(call_entry)
        raise ConnectionError(
            f"Toutes les tentatives ont échoué pour '{method}' : {last_error}"
        )
