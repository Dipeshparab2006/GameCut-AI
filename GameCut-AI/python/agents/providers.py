import os
import requests
from abc import ABC, abstractmethod
from .prompts import SYSTEM_PROMPT

class LLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str) -> str | None:
        """Generates a response from the LLM."""
        pass

class OllamaProvider(LLMProvider):
    def __init__(self):
        self.url = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
        self.model = os.getenv("OLLAMA_MODEL", "llama3")
        self.timeout = int(os.getenv("OLLAMA_TIMEOUT", 120))
        self.temperature = float(os.getenv("OLLAMA_TEMPERATURE", 0.2))

    def generate(self, prompt: str) -> str | None:
        """Sends a prompt to a local Ollama instance and returns the response."""
        print(f"Querying Ollama provider with model '{self.model}'...")
        try:
            response = requests.post(
                self.url,
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "system": SYSTEM_PROMPT,
                    "stream": False,
                    "options": {
                        "temperature": self.temperature,
                        "num_predict": 1024,
                    },
                },
                timeout=self.timeout,
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("response", "")
            else:
                print(f"Ollama returned status {response.status_code}: {response.text}")
                return None

        except requests.exceptions.ConnectionError:
            print("Ollama not running or connection refused. Is the OLLAMA_URL correct?")
            return None
        except requests.exceptions.Timeout:
            print(f"Ollama request timed out after {self.timeout} seconds.")
            return None
        except Exception as e:
            print(f"An unexpected error occurred with the Ollama provider: {e}")
            return None

class DeterministicProvider(LLMProvider):
    """
    A mock provider that doesn't call an LLM.
    It returns None to trigger the fallback mechanism.
    Useful for testing the fallback path or for environments without an LLM.
    """
    def generate(self, prompt: str) -> str | None:
        print("Using DeterministicProvider. No LLM will be called. Triggering fallback.")
        return None


def get_provider() -> LLMProvider:
    """
    Factory function to get the configured LLM provider.
    Reads from environment variables to decide which provider to instantiate.
    """
    provider_name = os.getenv("LLM_PROVIDER", "ollama").lower()

    if provider_name == "ollama":
        # Check if Ollama is intended to be used but is disabled for this run
        if os.getenv("NO_AGENT", "false").lower() == "true":
            print("NO_AGENT flag is set. Using deterministic provider.")
            return DeterministicProvider()
        return OllamaProvider()
    
    elif provider_name == "deterministic":
        return DeterministicProvider()
        
    # Future providers can be added here
    # elif provider_name == "openai":
    #     return OpenAIProvider()

    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {provider_name}. Supported: 'ollama', 'deterministic'.")