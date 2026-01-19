class InvalidEmbeddingModelError(TypeError):
    """The embedding model is not valid."""

    def __init__(self, received_type: type):
        super().__init__(
            f"Expected an Embeddings object, but got {received_type}"
        )
        self.received_type = received_type


class LLMInitializationError(RuntimeError):
    """Failed to initialize the LLM model."""

    def __init__(self, provider: str, model: str, original_error: Exception):
        super().__init__(
            f"Failed to initialize LLM (provider: {provider}, model: {model}): {original_error}"
        )
        self.provider = provider
        self.model = model
        self.original_error = original_error


class LLMStreamError(RuntimeError):
    """Failed to stream response from the LLM."""

    def __init__(self, original_error: Exception):
        super().__init__(f"Failed to stream LLM response: {original_error}")
        self.original_error = original_error
