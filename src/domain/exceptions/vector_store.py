class VectorStoreInitializationError(RuntimeError):
    """Failed to initialize the vector store."""

    def __init__(self, persist_dir: str, original_error: Exception):
        super().__init__(
            f"Failed to initialize vector store at '{persist_dir}': {original_error}"
        )
        self.persist_dir = persist_dir
        self.original_error = original_error


class VectorStoreWriteError(RuntimeError):
    """Failed to write documents to the vector store."""

    def __init__(self, playlist_id: str, original_error: Exception):
        super().__init__(
            f"Failed to save documents for playlist '{playlist_id}': {original_error}"
        )
        self.playlist_id = playlist_id
        self.original_error = original_error


class RetrieverError(RuntimeError):
    """Failed to retrieve relevant documents."""

    def __init__(self, query: str, original_error: Exception):
        super().__init__(
            f"Failed to retrieve documents for query '{query[:50]}...': {original_error}"
        )
        self.query = query
        self.original_error = original_error
