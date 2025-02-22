import asyncio
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import BaseModel, NonNegativeInt
from structlog import get_logger

logger = get_logger()

RENDER_SEMAPHORE = asyncio.Semaphore(1)


@cache
def template() -> str:
    return (Path(__file__).parent.parent / "labels/main.tex").read_text()


@dataclass
class CompilationError(RuntimeError):
    tex: str
    stdout: bytes
    stderr: bytes
    returncode: int


async def compile_tex(tex: str) -> bytes:
    async with RENDER_SEMAPHORE:
        with TemporaryDirectory() as tmpdir:
            outf = Path(tmpdir, "label.tex")
            pdf = Path(tmpdir, "label.pdf")
            outf.write_text(tex)
            proc = await asyncio.create_subprocess_exec(
                "latexmk",
                "-pdf",
                "-cd",
                outf,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if pdf.exists():
                logger.info(
                    "Successfully compiled label",
                    stdout=stdout.decode(),
                    stderr=stderr.decode(),
                    returncode=proc.returncode,
                )
                return pdf.read_bytes()
            else:
                assert proc.returncode
                raise CompilationError(tex, stdout, stderr, proc.returncode)


class Label(BaseModel):
    qr_contents: str
    no: NonNegativeInt
    title: str

    def render(self) -> str:
        # yes, we could use jinja, but it's overkill here
        # (and we'd have to change the env)
        return (
            template()
            .replace("QR_CONTENTS", self.qr_contents)
            .replace("NO", str(self.no))
            .replace("TITLE", self.title)
        )

    async def compile(self) -> bytes:
        tex = self.render()
        return await compile_tex(tex)

    async def show(self) -> None:
        """Show in pdf viewer, for testing."""
        with TemporaryDirectory() as tmpdir:
            pdf = await self.compile()
            outf = Path(tmpdir, "label.pdf")
            outf.write_bytes(pdf)
            proc = await asyncio.subprocess.create_subprocess_exec("zathura", outf)
            await proc.communicate()
