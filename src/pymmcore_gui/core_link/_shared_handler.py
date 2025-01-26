from pymmcore_plus.mda.handlers import (
    ImageSequenceWriter,
    OMETiffWriter,
    OMEZarrWriter,
    TensorStoreHandler,
)


class Handler:
    """Shared handler instance.

    This class is used to create a HANDLER singleton instance that can be shared
    across multiple classes (e.g. MDAWidget and ViewersCoreLink).
    """

    def __init__(self):
        self.handler: (
            OMEZarrWriter
            | OMETiffWriter
            | TensorStoreHandler
            | ImageSequenceWriter
            | None
        ) = None

    def set(
        self,
        handler: (
            OMEZarrWriter
            | OMETiffWriter
            | TensorStoreHandler
            | ImageSequenceWriter
            | None
        ),
    ) -> None:
        """Set the handler."""
        self.handler = handler

    def get(
        self,
    ) -> (
        OMEZarrWriter
        | OMETiffWriter
        | TensorStoreHandler
        | ImageSequenceWriter
        | None
    ):
        """Get the handler."""
        return self.handler


# Create a shared instance of the handler
HANDLER = Handler()
