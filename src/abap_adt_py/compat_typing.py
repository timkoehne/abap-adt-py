from typing import Optional, Dict, List  # Always available since Python 3.5

try:
    # Python 3.11+ where all are in typing
    from typing import Literal, NotRequired, TypeAlias, TypedDict
except ImportError:
    try:
        # Python 3.8 - 3.10: Literal in typing, others from typing_extensions
        from typing import Literal
        from typing_extensions import NotRequired, TypeAlias, TypedDict
    except ImportError:
        # Python 3.7 fallback: all from typing_extensions
        from typing_extensions import Literal, NotRequired, TypeAlias, TypedDict
