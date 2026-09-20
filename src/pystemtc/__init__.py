"""pySTEMTC: a headless Python port of STEM (Short Time-series Expression Miner).

pySTEMTC is a derivative work of STEM v1.3.14 (Java), authored by Jason Ernst,
Dima Patek and Ziv Bar-Joseph (https://ernstlab.github.io/STEM/).  The original
STEM is licensed under GPL-3.0; this port is therefore distributed under the
GNU General Public License v3.0 as well.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program.  If not, see <https://www.gnu.org/licenses/>.
"""

__version__ = "1.0.0"

from .config import STEMConfig
from .dataset import STEMDataset, SpotSet
from .engine import STEM
from .errors import STEMTCValueError
from .result import GeneAssignment, ProfileRecord, STEMResult

__all__ = [
    "STEM",
    "STEMResult",
    "STEMConfig",
    "STEMDataset",
    "SpotSet",
    "ProfileRecord",
    "GeneAssignment",
    "STEMTCValueError",
    "__version__",
]
