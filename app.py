import datetime
import logging
import sys
from typing import List

import folium
import streamlit as st
from folium.plugins import Draw
from mapa import convert_bbox_to_stl
from mapa.caching import get_hash_of_geojson
from mapa.utils import TMPDIR
from streamlit_folium import st_folium

from mapa_streamlit.cleaning import run_cleanup_job
from mapa_streamlit.settings import (
    ABOUT,
    BTN_LABEL_CREATE_STL,
    BTN_LABEL_DOWNLOAD_STL,
    DISK_CLEANING_THRESHOLD,
    MAP_CENTER,
    MAP_ZOOM,
    MAX_NUMBER_OF_STAC_ITEMS,
    ZOffsetSlider,
    ZScaleSlider,
)

log = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
log.addHandler(handler)


def _show_map(center: List[float], zoom: int) -> folium.Map:
    m = folium.Map(
        location=center,
        zoom_start=zoom,
        tiles="https://{s}.tile.opentopomap.org/{z}/{x}/{y}.png",
        attr='Map data: &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, <a href="http://viewfinderpanoramas.org">SRTM</a> | Map style: &copy; <a href="https://opentopomap.org">OpenTopoMap</a> (<a href="https://creativecommons.org/licenses/by-sa/3.0/">CC-BY-SA</a>)',  # noqa: E501
    )
    Draw(
        export=False,
        position="topleft",
        draw_options={
            "polyline": False,
            "poly": False,
            "circle": False,
            "polygon": False,
            "marker": False,
            "circlemarker": False,
        },
    ).add_to(m)
    return m


def _compute_stl(folium_output: dict, progress_bar: st.progress):
    if folium_output["last_active_drawing"] is None:
        # this line should never be reached, since the button is deactivated in the given if clause
        st.sidebar.warning("You need to draw a rectangle on the map first!")
    else:
        geometry = folium_output["last_active_drawing"]["geometry"]
        geo_hash = get_hash_of_geojson(geometry)
        mapa_cache_dir = TMPDIR()
        run_cleanup_job(path=mapa_cache_dir, disk_cleaning_threshold=DISK_CLEANING_THRESHOLD)
        path = mapa_cache_dir / f"{geo_hash}.stl"
        progress_bar.progress(0)
        try:
            convert_bbox_to_stl(
                bbox_geometry=geometry,
                z_scale=ZScaleSlider.value if z_scale is None else z_scale,
                z_offset=ZOffsetSlider.value if z_offset is None else z_offset,
                output_file=path,
                max_number_of_stac_items=MAX_NUMBER_OF_STAC_ITEMS,
                progress_bar=progress_bar,
            )
            # it is important to spawn this success message in the sidebar, because state will get lost otherwise
            st.sidebar.success("Successfully computed STL file!")
        except ValueError:
            st.sidebar.warning(
                "Selected region is too large, fetching data for this area would consume too many resources. "
                "Please select a smaller region."
            )


def _download_btn(data: str, disabled: bool) -> None:
    st.sidebar.download_button(
        label=BTN_LABEL_DOWNLOAD_STL,
        data=data,
        file_name=f'{datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}_mapa-streamlit.stl',
        disabled=disabled,
    )


if __name__ == "__main__":
    st.set_page_config(
        page_title="mapa",
        page_icon="🌍",
        layout="wide",
        initial_sidebar_state="expanded",
        menu_items={"About": ABOUT},
    )

    st.markdown(
        """
        # mapa &nbsp; 🌍 &nbsp; Map to STL Converter
        Follow the instructions in the sidebar on the left to create and download a 3D-printable STL file.
        """,
        unsafe_allow_html=True,
    )
    st.write("\n")
    m = _show_map(center=MAP_CENTER, zoom=MAP_ZOOM)
    output = st_folium(m, key="init", width=1000, height=600)

    geo_hash = None
    if output:
        if output["last_active_drawing"] is not None:
            geometry = output["last_active_drawing"]["geometry"]
            geo_hash = get_hash_of_geojson(geometry)

    # ensure progress bar resides at top of sidebar and is invisible initially
    progress_bar = st.sidebar.progress(0)
    progress_bar.empty()

    # Getting Started container
    with st.sidebar.container():
        st.markdown(
            f"""
            # Getting Started
            1. Click the black square on the map
            2. Draw a rectangle over your region of intereset (The larger the region the longer the STL file creation takes ☝️)
            3. Click on <kbd>{BTN_LABEL_CREATE_STL}</kbd>
            """,
            unsafe_allow_html=True,
        )
        st.button(
            BTN_LABEL_CREATE_STL,
            key="create_stl",
            on_click=_compute_stl,
            kwargs={"folium_output": output, "progress_bar": progress_bar},
            disabled=False if geo_hash else True,
        )
        st.markdown(
            f"""
            4. Wait for the computation to finish
            5. Click on <kbd>{BTN_LABEL_DOWNLOAD_STL}</kbd>
            """,
            unsafe_allow_html=True,
        )

    stl_path = TMPDIR() / f"{geo_hash}.stl"
    if stl_path.is_file():
        with open(stl_path, "rb") as fp:
            _download_btn(fp, False)
    else:
        _download_btn(b"None", True)

    st.sidebar.markdown("---")

    # Customization container
    with st.sidebar.container():
        st.write(
            """
            # Customization
            Use below options to customize the output STL file:
            """
        )
        z_offset = st.slider(ZOffsetSlider.label, ZOffsetSlider.min_value, ZOffsetSlider.max_value, ZOffsetSlider.value)
        z_scale = st.slider(
            ZScaleSlider.label,
            ZScaleSlider.min_value,
            ZScaleSlider.max_value,
            ZScaleSlider.value,
        )