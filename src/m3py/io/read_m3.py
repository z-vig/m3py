# Standard Libraries
from dataclasses import dataclass
from pathlib import Path
import os
from typing import Optional

# Top-Level Imports
from m3py.PDSretrieval import M3FileConfig
from m3py.constants import M3DataFormat

# Dependencies
import numpy as np

type pathlike = str | os.PathLike


@dataclass
class Window:
    """
    Class for keeping track of window information for image viewing.
    The user will specify the bottom left row (X) and column (Y) of the window
    as well as the width and height as shown below:
    """
    X: int
    Y: int
    W: int
    H: int


def read_m3(
    img_path: str | os.PathLike,
    data_format: M3DataFormat,
    acq_type: str,
    window: Optional[Window] = None,
):
    img_path = Path(img_path)

    nbands = getattr(data_format, acq_type).nbands
    ncols = getattr(data_format, acq_type).ncols
    dtype = getattr(data_format, acq_type).dtype
    hdrlen = getattr(data_format, acq_type).header_length

    if dtype == "<d":
        nbytes = 64 // 8
        numpy_dtype = np.float64
    elif dtype == "<f":
        nbytes = 32 // 8
        numpy_dtype = np.float32
    elif dtype == "<h":
        nbytes = 16 // 8
        numpy_dtype = np.int16
    else:
        numpy_dtype = None
        raise ValueError(f"{dtype} is an invalid dtype.")

    full_col_bytes = hdrlen + (ncols * nbands * nbytes)

    total_rows = os.path.getsize(img_path) // full_col_bytes

    if window is None:
        window = Window(0, 0, ncols, total_rows)

    start_row = window.Y
    col_offset = hdrlen + (window.X * nbands * nbytes)
    start_byte = (start_row * full_col_bytes)
    col_end_buffer = (ncols - (window.X + window.W)) * nbytes

    # Validating Window
    xbounds_chk = (window.X + window.H) > total_rows
    ybounds_chk = (window.Y + window.W) > ncols
    if xbounds_chk and not ybounds_chk:
        raise ValueError("Window does not fit within X bounds.")
    elif ybounds_chk and not xbounds_chk:
        raise ValueError("Window does not fit within Y bounds.")
    elif xbounds_chk and ybounds_chk:
        raise ValueError("Window does not fit within either X or Y bounds.")

    window_data = np.empty([window.H, window.W, nbands], dtype=numpy_dtype)

    with open(img_path, "rb") as f:
        byte_index = 0
        f.seek(start_byte)
        byte_index = f.tell()
        for i in range(0, window.H):
            f.seek(col_offset + byte_index)
            for j in range(0, nbands):
                bindat = f.read(window.W * nbytes)
                byte_index = f.tell()
                f.seek(byte_index + col_end_buffer)
                row = np.frombuffer(bindat, dtype=dtype)
                window_data[i, :, j] = row
                byte_index = f.tell()

    if window_data.shape[1] == 320:
        window_data = window_data[:, ::-1, :]

    return window_data


def get_wavelengths(
    file_config: M3FileConfig | None = None,
    rfl_hdr: Optional[pathlike] = None,
    acq_type: Optional[str] = None
):
    """
    Returns a list of wavelengths from reflectance header file.

    Parameters
    ----------
    file_config: M3FileConfig
        M3 File Config object.
    rfl_hdr: str | os.PathLike
        Path to reflectance header file.
    acq_type: str
        Either `"global"` or `"targeted"`.

    """
    # print(file_config.acq_type)
    if file_config is not None:
        rfl_hdr_path = file_config.pds_dir.l2.rfl_hdr
        acq = file_config.acq_type
    else:
        if rfl_hdr is None or acq_type is None:
            raise ValueError("Must provide both rfl_hdr and acq_type if no"
                             "file_config.")
        rfl_hdr_path = Path(rfl_hdr)
        acq = acq_type

        assert isinstance(rfl_hdr_path, Path)
        assert acq in ("global", "targeted")

    if acq == 'global':
        loc_key = "wavelength = {"
    elif acq == 'targeted':
        loc_key = "target wavelengths = {"
    else:
        raise ValueError(f"{acq} is an invalid acq_type. Must be "
                         "either global or targeted.")

    with open(rfl_hdr_path, "r") as f:
        fread = f.read()
        idx_start = fread.find(loc_key)
        idx_end = fread.find("}", idx_start)
        str_list = fread[idx_start:idx_end].split("\n")[1:]
        num_list = [float(i.replace(" ", "").replace(",", ""))
                    for i in str_list]
    return num_list
