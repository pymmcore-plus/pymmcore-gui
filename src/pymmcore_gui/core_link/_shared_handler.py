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
        return self.handler


# Create a shared instance of the handler
HANDLER = Handler()
