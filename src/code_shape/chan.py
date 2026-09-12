"""code_shape.chan — BaseChan integration for Morphē-chan."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from basic_chan import BaseChan, ChanIdentity
from shape_analyzer import CodeShapeAnalyzer


class MorpheChan(BaseChan):
    """Geometric Code Analysis & Synthesis Sister."""

    def __init__(self, project_root: Optional[Path | str] = None):
        identity = ChanIdentity(
            name="Morphē-chan",
            slug="morphe-chan",
            japanese_name="モルペー・ちゃん",
            tagline="Multi-dimensional geometric code analysis, vector representation, and synthesis.",
            version="0.1.0",
        )
        super().__init__(identity=identity, project_root=project_root)

    def initialize(self) -> None:
        """Initialize shape analyzer and register tools."""
        self.analyzer = CodeShapeAnalyzer()

        @self.tools.register(
            name="analyze_code_shape",
            description="Analyze multi-dimensional geometric code shape of a file or code snippet.",
        )
        def analyze_code_shape(file_path: str) -> Dict[str, Any]:
            p = Path(file_path)
            if not p.is_absolute():
                p = self.root / p
            return self.analyzer.analyze_file(str(p))

        @self.tools.register(
            name="compare_code_shapes",
            description="Compare geometric shape similarity between two code files or functions.",
        )
        def compare_code_shapes(path_a: str, path_b: str) -> Dict[str, Any]:
            pa = Path(path_a) if Path(path_a).is_absolute() else self.root / path_a
            pb = Path(path_b) if Path(path_b).is_absolute() else self.root / path_b
            res = self.analyzer.compare_files(str(pa), str(pb))
            return {"similarity": res}


def get_chan() -> MorpheChan:
    """Entrypoint factory for basic_chan sister discovery."""
    return MorpheChan()


# Default instance
morphe_chan = MorpheChan()
