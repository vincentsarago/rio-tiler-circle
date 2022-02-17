"""rio_tiler_circle.reader."""

import math
from typing import Any, Dict, Optional

import attr
import rio_tiler
from morecantile import BoundingBox, Tile
from rio_tiler.errors import IncorrectTileBuffer, TileOutsideBounds
from rio_tiler.models import ImageData
from rio_tiler.types import Indexes, NumType
from rio_tiler.utils import create_cutline


@attr.s
class COGReader(rio_tiler.io.COGReader):
    """Custom COGReader."""

    def tile(
        self,
        tile_x: int,
        tile_y: int,
        tile_z: int,
        tilesize: int = 256,
        indexes: Optional[Indexes] = None,
        expression: Optional[str] = None,
        tile_buffer: Optional[NumType] = None,
        **kwargs: Any,
    ) -> ImageData:
        """Read a Web Map tile from a COG.

        Args:
            tile_x (int): Tile's horizontal index.
            tile_y (int): Tile's vertical index.
            tile_z (int): Tile's zoom level index.
            tilesize (int, optional): Output image size. Defaults to `256`.
            indexes (int or sequence of int, optional): Band indexes.
            expression (str, optional): rio-tiler expression (e.g. b1/b2+b3).
            tile_buffer (int or float, optional): Buffer on each side of the given tile. It must be a multiple of `0.5`. Output **tilesize** will be expanded to `tilesize + 2 * tile_buffer` (e.g 0.5 = 257x257, 1.0 = 258x258).
            kwargs (optional): Options to forward to the `COGReader.part` method.

        Returns:
            rio_tiler.models.ImageData: ImageData instance with data, mask and tile spatial info.

        """
        if not self.tile_exists(tile_x, tile_y, tile_z):
            raise TileOutsideBounds(
                f"Tile {tile_z}/{tile_x}/{tile_y} is outside {self.input} bounds"
            )

        tile_bounds = self.tms.xy_bounds(Tile(x=tile_x, y=tile_y, z=tile_z))
        if tile_buffer is not None:
            if tile_buffer % 0.5:
                raise IncorrectTileBuffer(
                    "`tile_buffer` must be a multiple of `0.5` (e.g: 0.5, 1, 1.5, ...)."
                )

            x_res = (tile_bounds.right - tile_bounds.left) / tilesize
            y_res = (tile_bounds.top - tile_bounds.bottom) / tilesize

            # Buffered Tile Bounds
            tile_bounds = BoundingBox(
                tile_bounds.left - x_res * tile_buffer,
                tile_bounds.bottom - y_res * tile_buffer,
                tile_bounds.right + x_res * tile_buffer,
                tile_bounds.top + y_res * tile_buffer,
            )

            # Buffered Tile Size
            tilesize += int(tile_buffer * 2)

        center = (
            (tile_bounds[0] + tile_bounds[2]) / 2,
            (tile_bounds[1] + tile_bounds[3]) / 2,
        )
        radius = (tile_bounds[2] - tile_bounds[0]) / 2

        feat: Dict[Any, Any] = {
            "type": "Feature",
            "properties": {},
            "geometry": {"type": "Polygon", "coordinates": [[]]},
        }
        for theta in range(0, 360, 10):
            x = center[0] + radius * math.cos(math.radians(theta))
            y = center[1] + radius * math.sin(math.radians(theta))
            feat["geometry"]["coordinates"][0].append([x, y])

        cutline = create_cutline(self.dataset, feat, geometry_crs=self.tms.rasterio_crs)
        vrt_options = kwargs.pop("vrt_options", {})
        vrt_options.update({"cutline": cutline})

        return self.part(
            tile_bounds,
            dst_crs=self.tms.rasterio_crs,
            bounds_crs=None,
            height=tilesize,
            width=tilesize,
            max_size=None,
            indexes=indexes,
            expression=expression,
            vrt_options=vrt_options,
            **kwargs,
        )
