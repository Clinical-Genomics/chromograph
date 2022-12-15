"""Plot chromosoms and misc variants. Can be invoked from commandline
or from imported.

    $ ./chromograph.py --cyt cytoBand.bed

Further info:
  https://matplotlib.org/3.1.1/api/collections_api.html#matplotlib.collections.BrokenBarHCollection


Project on Github:

    https://github.com/mikaell/chromograph

"""
import os
import re
import sys
from argparse import ArgumentParser

import matplotlib
import pandas
from matplotlib import pyplot as plt
from matplotlib.collections import BrokenBarHCollection

from chromograph import __version__

from .chr_utils import (
    chr_type_format,
    filter_dataframe,
    outpath,
    parse_bed,
    parse_upd_regions,
    parse_wig_declaration,
)

matplotlib.use("Agg")


# TODO: instead of padding look-ahead and contsrict if overlap
# TODO: combined ROH image

HELP_STR_COMBINE = "Write all graphs to one file (default one plot per file)"
HELP_STR_COV = "Plot coverage from fixed step wig file"
HELP_STR_EU = "Always output an euploid amount of files -even if some are empty"
HELP_STR_EXOM = "Plot exom coverage from bed-file"
HELP_STR_IDEO = "Plot ideograms from bed-file on format {}"
HELP_STR_NORM = "Normalize data (wig/coverage)"
HELP_STR_RGB = "Set color (RGB hex, only with --coverage option)"
HELP_STR_UPD_REGIONS = "Plot UPD regions from bed file"
HELP_STR_UPD_SITE = "Plot UPD sites from bed file "
HELP_STR_EXOM = "Plot exom coverage from bed file "
HELP_STR_VSN = "Display program version ({}) and exit."

DPI_SMALL = 100
DPI_MEDIUM = 300
DPI_LARGE = 1000
PADDING = 200000
CHROM_END_POS = 249255000  # longest chromosome is #1, 248,956,422 base pairs
HEIGHT = 1
YBASE = 0
SPACE = 1
FIGSIZE = (6, 8)  # 7750 x 385
FIGSIZE_WIG = (8.05, 0.685)  # 7750 x 385
FIGSIZE_SINGLE = (8, 8)
UPD_FORMAT = ["chrom", "start", "end", "updType"]
ROH_BED_FORMAT = ["chrom", "start", "end"]
IDEOGRAM_FORMAT = ["chrom", "start", "end", "name", "gStain"]
EXOM_FORMAT = [
    "chrom",
    "start",
    "end",
    "F3",
    "F4",
    "F5",
    "F6",
    "readCount",
    "meanCoverage",
    "percentage10",
    "percentage15",
    "percentage20",
    "percentage50",
    "percentage100",
    "sampleName",
]
EXOM_GAP = 10000

WIG_FORMAT = ["chrom", "coverage", "pos"]
WIG_ORANGE = "#DB6400"
WIG_MAX = 70.0
DARK_GOLD = "#A98200"

TRANSPARENT_PNG = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x10\x00\x00\x00\x10\x01\x03\x00\x00\x00%=m"\x00\x00\x00\x03PLTE\xff\xff\xff\xa7\xc4\x1b\xc8\x00\x00\x00\x01tRNS\x00@\xe6\xd8f\x00\x00\x00\x0cIDAT\x08\x1dc` \r\x00\x00\x000\x00\x01\x84\xac\xf1z\x00\x00\x00\x00IEND\xaeB`\x82'


CHROMOSOMES = [
    "1",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "8",
    "9",
    "10",
    "11",
    "12",
    "13",
    "14",
    "15",
    "16",
    "17",
    "18",
    "19",
    "20",
    "21",
    "22",
    "M",
    "X",
    "Y",
]

DEFAULT_SETTING = {
    "combine": False,
    "normalize": False,
    "euploid": False,
    "agg_chunk_size": 10000,
    "dpi": DPI_MEDIUM,
}

get_color = {
    # Cytoband colors
    "acen": "#b56666",
    "gneg": "#fafafa",
    "gpos100": "#121212",
    "gpos25": "#666666",
    "gpos50": "#606060",
    "gpos75": "#2e2e2e",
    "gvar": "#777777",
    "stalk": "#444444",
    # UPD sites colors
    "ANTI_UPD": "#509188",  # Medium green
    "PB_HETEROZYGOUS": "#35605A",  # Dark slate greenish gray
    "PB_HOMOZYGOUS": "#6B818C",  # Slate gray
    "UNINFORMATIVE": "#FFFFFF",  # White
    "UPD_MATERNAL_ORIGIN": "#aa2200",  # Red
    "UPD_PATERNAL_ORIGIN": "#0044ff",  # Blue
    # UPD region colors
    "HETERODISOMY/DELETION": "#BDB76B",  # Dark khaki
    "ISODISOMY/DELETION": "#FFE4B5",  # Moccasin
    "MATERNAL": "#aa2200",
    "PATERNAL": "#0044ff",  # Blue
    # Heterodisomy colors
    "MATERNAL_LIGHT": "#F48C95",  # Light Red
    "PATERNAL_LIGHT": "#6C88FF",  # Light blue
    # Exom
    "EXOM_COV": "#FF5965",  # Salmon red
}


# TODO: skapa pytest med md5-sum för att automatisera körningar


## MatPlotLib: Functions to yield input for MatPlotLib
## ---------------------------------------------------
def horizontal_bar_generator_combine(dataframe, y_positions):
    """Iterate dataframe

    Args:
        dataframe(pandas dataframe)
        y_positions()
        height
    Yields:
        BrokenBarHCollection
    """
    for chrom, group in dataframe.groupby("chrom"):
        print("chrom: {}".format(chrom))
        yrange = (y_positions[chrom], HEIGHT)
        xranges = group[["start", "width"]].values
        yield BrokenBarHCollection(xranges, yrange, facecolors=group["colors"], label=chrom)


def horizontal_bar_generator(dataframe):
    """Iterate dataframe and create horizontal bar graphs for printing
    Yeilds:
    Brokenbarhcollection --from BED DF to be plotted
    """
    for chrom, group in dataframe.groupby("chrom"):
        yrange = (0, HEIGHT)
        xranges = group[["start", "width"]].values
        yield BrokenBarHCollection(xranges, yrange, facecolors=group["colors"], label=chrom)


def vertical_bar_generator(dataframe, x_axis, y_axis):
    """Iterate dataframe and yeild dict representing an vertical bar graph i.e. coverage"""
    for chrom, group in dataframe.groupby("chrom"):
        yield {
            "label": chrom,
            "x": group[x_axis].values,
            "y": group[y_axis].values,
            "bar_width": group["bar_width"].values,
        }


def area_graph_generator(dataframe, x_axis, y_axis):
    """Iterate dataframe and yeild dict representing an area graph i.e. coverage"""
    for chrom, group in dataframe.groupby("chrom"):
        yield {
            "label": chrom,
            "x": group[x_axis].values,
            "y": group[y_axis].values,
        }


def area_graph_generator_combine(dataframe, height):
    # TODO: combining area graphs into one png is not implemented
    yield False


## Library functions
## -----------------
def _assure_dir(outd):
    """Create directory 'outd' if it does not exist"""
    print("outd: {}".format(outd))
    if not os.path.exists(outd):
        os.makedirs(outd)


def _common_settings(axis):
    """Common Matplotlib settings to remove visible axis"""
    axis.get_xaxis().set_visible(False)
    axis.get_yaxis().set_visible(False)
    axis.set_axis_off()  # Remove black line surrounding pic.


def _get_chromosome_list(kind):
    """Return list of chromsome names, on format '12' or 'chr12'"""
    if kind == "str":
        return ["chr" + chr for chr in CHROMOSOMES]
    return CHROMOSOMES


def _is_chr_str(chrom):
    """Assume that chromsome in bed/wig files are on format 'chr22' or '22', upon
    which int or str is returned."""
    try:
        int(chrom)
        return "int"
    except:
        return "str"


def _read_dataframe(filepath, format):
    """Read a bed file into a Pandas dataframe according to 'format'. Do
    some checks and return dataframe"""
    dataframe = pandas.read_csv(filepath, dtype={"chrom": str}, names=format, sep="\t", skiprows=1)
    # dataframe = pandas.read_csv(filepath, dtype={'chrom':str, 'start':int,  'end':int,'meanCoverage':int}, names=format, sep="\t", skiprows=1)
    if dataframe.empty:
        print("Warning: No suitable data found: {}!".format(filepath))
        sys.exit(0)
    # cast chromosome to string (read as int)
    dataframe.chrom = dataframe.chrom.astype(str)
    # delete chromosomes not in CHROMOSOME_LIST
    chromosome_list = _get_chromosome_list(_is_chr_str(dataframe.chrom[0]))
    return filter_dataframe(dataframe, chromosome_list)


def _get_tint_color(disomy_type, parent):
    """If heterodisomy return a lighter color"""
    if disomy_type == "heterodisomy":
        return get_color[parent + "_LIGHT"]
    if disomy_type == "homodisomy/deletion":
        return get_color["ISODISOMY/DELETION"]
    if disomy_type == "isodisomy/deletion":
        return get_color["ISODISOMY/DELETION"]
    if disomy_type == "heterodisomy/deletion":
        return get_color["HETERODISOMY/DELETION"]
    return get_color[parent]


def parse_lib_call(args):
    """Helper function to keep command line and import usage of Chromograph the same"""
    arg_dict = {}
    arg_dict["combine"] = "combine" in args
    arg_dict["normalize"] = "normalize" in args
    arg_dict["euploid"] = "euploid" in args
    return arg_dict


def _args_to_dict(filepath, args):
    """Handle command line arguments and settings. Return a dict of
    args set to default if not given.


    Arguments
        filepath : File
        args: Tuple

    Returns: Dict
    """
    print("ARGS______")
    print(args)
    settings = DEFAULT_SETTING
    settings["outd"] = os.path.dirname(filepath)
    head, *_tail = list(args)
    print(head.get("small"))

    settings["combine"] = head.get("combine") == "combine"
    settings["normalize"] = head.get("norm") == "norm"
    settings["euploid"] = head.get("euploid") == "euploid"
    if "outd" in head and head["outd"] is not None:
        _assure_dir(head["outd"])
        settings["outd"] = head["outd"]
    settings["step"] = head.get("step")
    if head.get("small"):
        settings["dpi"] = DPI_SMALL
    elif head.get("large"):
        settings["dpi"] = DPI_LARGE
    else:
        settings["dpi"] = DPI_MEDIUM

    print("SETTINGS")
    print(settings)
    return settings


def _wig_args_to_dict(header, filepath, args):
    """Override default settings if argument is given, return settings dict for coverage/wig"""
    settings = _args_to_dict(filepath, args)
    settings["color"] = WIG_ORANGE  # set default color, override if rgb in kw
    settings["fixedStep"] = header["step"]
    if "rgb" in args and args.rgb is not None:
        settings["color"] = _rgb_str(args.rgb)
    if "step" in args and args.step is not None:
        settings["fixedStep"] = args.step
    return settings


def _rgb_str(color):
    """Return hex color as string"""
    head, *_tail = str(color)
    if head == "#":
        return color  # color was alread on format "#123456"
    return "#" + str(color)


def regions_to_hbar(region_list_chr):
    """Make a MathPlotLIb 'BrokenbarCollection' from upd sites data,
    Isodisomy will have one block and one color. Heterodisomy will
    be two adjecent bars with two colors. Both plots will have a
    transperant middle line for aestetics."""
    return_list = []
    for i in region_list_chr:
        hbar_upper = BrokenBarHCollection(
            i["xranges"], (0.52, 1), facecolors=i["upper"], label=i["chr"]
        )
        hbar_lower = BrokenBarHCollection(
            i["xranges"], (0, 0.48), facecolors=i["lower"], label=i["chr"]
        )
        return_list.append([hbar_upper, hbar_lower])
    return return_list


def region_to_dict(region):
    start = int(region["start"])
    width = int(region["stop"]) - int(region["start"])
    xranges = (start, width)
    disomy_type = region["desc"]["type"].lower()
    origin = region["desc"]["origin"]
    color = get_color[origin]
    upper_color = _get_tint_color(disomy_type, origin)

    hbar_upper = {"xranges": xranges, "facecolors": upper_color, "label": region["chr"]}
    hbar_lower = {"xranges": xranges, "facecolors": color, "label": region["chr"]}

    return {
        "chr": region["chr"],
        "xranges": xranges,
        "hbar_lower": color,
        "hbar_upper": upper_color,
    }


def compile_per_chrom(hbar_list):
    """Return [{chr: upper: lower:}]"""
    if hbar_list == []:
        return []

    mylist = []
    comp = {"chr": None, "xranges": [], "upper": [], "lower": []}
    mylist.append(comp)

    for i in hbar_list:
        # same chromosome, add to lists
        if mylist[-1]["chr"] is None:
            mylist[-1]["chr"] = i["chr"]
            mylist[-1]["xranges"].append(i["xranges"])
            mylist[-1]["upper"].append(i["hbar_upper"])
            mylist[-1]["lower"].append(i["hbar_lower"])
        elif mylist[-1]["chr"] == i["chr"]:
            mylist[-1]["xranges"].append(i["xranges"])
            mylist[-1]["upper"].append(i["hbar_upper"])
            mylist[-1]["lower"].append(i["hbar_lower"])
        else:
            mylist.append(
                {
                    "chr": i["chr"],
                    "xranges": [i["xranges"]],
                    "upper": [i["hbar_upper"]],
                    "lower": [i["hbar_lower"]],
                }
            )
    return mylist


## Functions to create PNGS
## ------------------------
# rename print_broken_horizontal_bar
def print_individual_pics(dataframe, infile, settings):
    """Print one chromosomes per image file"""
    outd = settings["outd"]
    euploid = settings["euploid"]
    resolution = settings["dpi"]
    fig = plt.figure(figsize=(10, 0.5))
    axis = fig.add_subplot(111)
    plt.rcParams.update({"figure.max_open_warning": 0})
    is_printed = []
    for collection in horizontal_bar_generator(dataframe):
        axis.add_collection(collection)
        _common_settings(axis)
        axis.set_xlim(0, CHROM_END_POS)  # bounds within maximum chromosome length
        plt.rcParams['figure.dpi'] = resolution
        plt.rcParams['savefig.dpi'] = resolution
        outfile = outpath(outd, infile, collection.get_label())
        print("outfile: {}".format(outfile))
        fig.savefig(outfile, transparent=True, bbox_inches="tight", pad_inches=0)
        axis.cla()  # clear canvas before next iteration
        is_printed.append(collection.get_label())
    if euploid:
        print_transparent_pngs(infile, outd, is_printed)


def print_combined_pic(dataframe, chrom_ybase, chrom_centers, infile, settings, chr_list):
    """Print all chromosomes in a single PNG picture"""
    outd = settings["outd"]
    fig = plt.figure(figsize=FIGSIZE)
    axis = fig.add_subplot(111)
    plt.rcParams['figure.dpi'] = settings["dpi"]
    plt.rcParams['savefig.dpi'] = settings["dpi"]

    for collection in horizontal_bar_generator_combine(dataframe, chrom_ybase):
        axis.add_collection(collection)

    axis.set_yticks([chrom_centers[i] for i in chr_list])
    axis.set_yticklabels(chr_list)
    axis.axis("tight")
    outfile = outpath(outd, infile, "combined")
    print("outfile: {}".format(outfile))
    fig.savefig(outfile, transparent=True, bbox_inches="tight", pad_inches=0, dpi=resolution)


def print_transparent_pngs(file, outd, is_printed):
    """Write an empty png file to disk for every chromosome what has, always including Y.
    Motivated by auxilary software not being able to handle missing output
    chromosome are missing in the wig."""

    gene_build = chr_type_format(is_printed[0])
    for chrom in CHROMOSOMES:
        if chrom in is_printed:
            continue
        if "chr" + chrom in is_printed:
            continue

        prefix = "chr" if gene_build == "str" else ""
        outfile = outpath(outd, file, prefix + chrom)
        print("print transparent: {}".format(outfile))
        filestream = open(outfile, "bw")
        filestream.write(TRANSPARENT_PNG)
        filestream.close()


def print_bar_chart(dataframe, filepath, x_axis, y_axis, color, ylim_height, settings):
    """Print vertical bar chart"""
    is_printed = []

    outd = settings["outd"]
    combine = settings["combine"]
    euploid = settings["euploid"]
    resolution = settings["dpi"]
    for chrom_data in vertical_bar_generator(dataframe, x_axis, y_axis):
        fig, axis = plt.subplots(figsize=FIGSIZE_WIG)
        _common_settings(axis)
        axis.bar(
            chrom_data["x"],
            chrom_data["y"],
            width=chrom_data["bar_width"],
            color=color,
            linewidth=0,
        )
        plt.ylim(0, ylim_height)
        plt.rcParams['figure.dpi'] = resolution
        plt.rcParams['savefig.dpi'] = resolution
        axis.set_ylim(bottom=0)
        fig.tight_layout()
        axis.set_xlim(0, CHROM_END_POS)  # bounds within maximum chromosome length
        outfile = outpath(outd, filepath, chrom_data["label"])
        print("outfile: {}".format(outfile))
        fig.savefig(outfile, transparent=True, bbox_inches="tight", pad_inches=0)
        is_printed.append(chrom_data["label"])
        plt.close(fig)  # save memory
    if euploid:
        print_transparent_pngs(filepath, outd, is_printed)


def wig_to_dataframe(infile, step, col_format):
    """Read a wig file into a Pandas dataframe.  Returns:  Dataframe"""
    filestream = open(infile, "r")
    coverage_data = []
    pos = 0
    chrom = ""
    for line in filestream.readlines():
        try:
            if line == "NaN\n":
                wig_value = 0
            else:
                wig_value = float(line)
            wig_value = wig_value if wig_value < WIG_MAX else WIG_MAX
            coverage_data.append([chrom, wig_value, pos])
            pos += step
        except ValueError:
            reresult = re.search("chrom=(\w*)", line)  # find chromosome name in line
            if reresult:
                start_pos = [chrom, 0, 1]  # write 0 in beginning, works against bug
                stop_pos = [chrom, 0, pos + 1]  # write 0 at end removes linear slope
                last_pos = [chrom, 0, CHROM_END_POS]  # write trailing char for scale when plotting
                #               coverage_data.insert(start_pos)
                coverage_data.append(stop_pos)
                coverage_data.append(last_pos)
                chrom = reresult.group(1)  # start working on next chromosome
                pos = 0
    filestream.close()
    dataframe = pandas.DataFrame(coverage_data, columns=col_format)
    return dataframe


def graph_coordinates(list_of_chromosomes):
    """Iterate through list of chromosomes and return X
    (as center for graph) and Y coordinates for plotting.

        Args:

        Returns:
            chrom_ybase(int)
            chrom_centers(int)
    """
    ybase = YBASE
    chrom_ybase = {}
    chrom_centers = {}
    for chrom in list_of_chromosomes:
        chrom_ybase[chrom] = ybase
        chrom_centers[chrom] = ybase + HEIGHT / 2.0
        ybase += HEIGHT + SPACE
    return chrom_ybase, chrom_centers


## Lib Interface
## -------------
def plot_autozyg(filepath, *args, **kwargs):
    _plot_autozyg(filepath, parse_lib_call(args) | kwargs)


def plot_coverage_wig(filepath, *args, **kwargs):
    _plot_coverage_wig(filepath, parse_lib_call(args) | kwargs)


def plot_exom_coverage(filepath, *args, **kwargs):
    _plot_exom_coverage(filepath, parse_lib_call(args) | kwargs)


def plot_homosnp_wig(filepath, *args, **kwargs):
    _plot_homosno_wig(filepath, parse_lib_call(args) | kwargs)


def plot_ideogram(filepath, *args, **kwargs):
    _plot_ideogram(filepath, parse_lib_call(args) | kwargs)


def plot_upd_regions(filepath, *args, **kwargs):
    _plot_upd_regions(filepath, parse_lib_call(args) | kwargs)


def plot_upd_sites(filepath, *args, **kwargs):
    _plot_upd_sites(filepath, parse_lib_call(args) | kwargs)


def plot_upd_sites(filepath, *args, **kwargs):
    _plot_upd_sites(filepath, parse_lib_call(args) | kwargs)


##
## ----------------------
def _plot_ideogram(filepath, *args):
    """Visualize chromosome ideograms from bed-file. Format:

    Args:
       args:argparse.Namespace

    Returns:
          None
    """
    settings = _args_to_dict(filepath, args)
    print(
        "Plot ideograms with settings\ncombine:{}\noutd:{}".format(
            settings["combine"], settings["outd"]
        )
    )

    dataframe = _read_dataframe(filepath, IDEOGRAM_FORMAT)
    dataframe["width"] = dataframe.end - dataframe.start
    dataframe["colors"] = dataframe["gStain"].apply(lambda x: get_color[x])
    chromosome_list = _get_chromosome_list(_is_chr_str(dataframe.chrom[0]))
    if settings["combine"]:
        chrom_ybase, chrom_centers = graph_coordinates(chromosome_list)
        print_combined_pic(
            dataframe, chrom_ybase, chrom_centers, filepath, settings["outd"], chromosome_list
        )
    else:
        print_individual_pics(dataframe, filepath, settings)


def _plot_autozyg(filepath, *args):
    """Plot ROH file for analysis of isodisomy"""
    settings = _args_to_dict(filepath, args)
    print(
        "Plot RoH Sites with settings\ncombine:{}\neuploid:{}".format(
            settings["combine"], settings["euploid"]
        )
    )
    dataframe = _read_dataframe(filepath, ROH_BED_FORMAT)
    dataframe["width"] = (dataframe.end - dataframe.start) + PADDING
    dataframe["colors"] = get_color["PB_HOMOZYGOUS"]
    chromosome_list = _get_chromosome_list(_is_chr_str(dataframe.chrom[0]))
    if settings["combine"]:
        chrom_ybase, chrom_centers = graph_coordinates(chromosome_list)
        print_combined_pic(
            dataframe, chrom_ybase, chrom_centers, filepath, settings["outd"], chromosome_list
        )
    else:
        print_individual_pics(dataframe, filepath, settings)


def _plot_upd_sites(filepath, *args):
    """Visualize UPD data from bed-file. Bed format as:

        Chromosome <tab> Start <tab> End <tab> Upd-type

    These can be generated with SV caller upd.py. It can be found at
    [https://github.com/bjhall/upd]

    Args:
        filepath<str> -- input file on wig format

    Optional Args:
        combine -- output all graphs in one png
        normalize -- normalize to mean
        outd=<str> -- output directory
    Returns: None

    """
    settings = _args_to_dict(filepath, args)

    print(
        "Plot UPD Sites with settings\ncombine:{}\neuploid:{}".format(
            settings["combine"], settings["euploid"]
        )
    )

    dataframe = _read_dataframe(filepath, UPD_FORMAT)
    dataframe["width"] = (dataframe.end - dataframe.start) + PADDING
    dataframe["colors"] = dataframe["updType"].apply(lambda x: get_color[x])
    chromosome_list = _get_chromosome_list(_is_chr_str(dataframe.chrom[0]))
    chrom_ybase, chrom_centers = graph_coordinates(chromosome_list)

    if settings["combine"]:
        print_combined_pic(
            dataframe, chrom_ybase, chrom_centers, filepath, settings["outd"], chromosome_list
        )
    else:
        print_individual_pics(dataframe, filepath, settings)


def _plot_exom_coverage(filepath, *args):
    """Plot exom coverage from bed file."""
    settings = _args_to_dict(filepath, args)
    ylim_height = 5
    x_axis = "start"
    y_axis = "bar_height"

    print(
        "Plot Exom coverage with settings\ncombine:{}\neuploid:{}".format(
            settings["combine"], settings["euploid"]
        )
    )

    # Regard exoms as one if distance between two adjecent entries are less than exom gap.
    # Weights of exoms included in such a added and divided by the total width to create
    # representative value (bar height).
    dataframe = _read_dataframe(filepath, EXOM_FORMAT)
    df = dataframe.drop(dataframe[dataframe.meanCoverage < 10.0].index).copy()
    mask = dataframe["start"].sub(dataframe["end"].shift(fill_value=0)).gt(EXOM_GAP).cumsum()
    dataframe["weight"] = (dataframe["end"] - dataframe["start"]) * dataframe["meanCoverage"]
    dataframe2 = dataframe.groupby([mask, "chrom"]).agg(
        start=("start", "first"), end=("end", "last"), sum=("weight", "sum")
    )
    dataframe2["bar_width"] = dataframe2["end"] - dataframe2["start"] + PADDING
    dataframe2["bar_height"] = dataframe2["sum"] / dataframe2["bar_width"]
    dataframe2["bar_height"].clip(upper=80, inplace=True)

    print_bar_chart(
        dataframe2,
        filepath,
        x_axis,
        y_axis,
        get_color["EXOM_COV"],
        settings,
        ylim_height,
    )


def _plot_coverage_wig(filepath, *args):
    """Plot a wig file representing coverage"""
    ylim_height = 75
    plot_wig_aux(filepath, ylim_height, WIG_ORANGE, args)


def _plot_homosnp_wig(filepath, *args):
    """Plot a wig file where entries represent percent of homozygous SNPs"""
    ylim_height = 1
    plot_wig_aux(filepath, ylim_height, DARK_GOLD, args)


def plot_wig_aux(filepath, ylim_height, default_color, args):
    """Outputs png:s of data given on WIG format."""
    header = parse_wig_declaration(filepath)
    settings = _wig_args_to_dict(header, filepath, args)

    print(
        "Plot WIG with settings \nstep: {}\noutd:{}\ncombine:{}\nnormalize:{}\neuploid:{}".format(
            settings["fixedStep"],
            settings["outd"],
            settings["combine"],
            settings["normalize"],
            settings["euploid"],
        )
    )

    chromosome_list = _get_chromosome_list(header["chrom"])
    dataframe = wig_to_dataframe(filepath, settings["fixedStep"], WIG_FORMAT)
    dataframe = filter_dataframe(
        dataframe, chromosome_list
    )  # delete chromosomes not in CHROMOSOMES

    x_axis = "pos"
    y_axis = "coverage"
    if settings["normalize"]:
        dataframe["normalized_coverage"] = (dataframe.coverage / dataframe.coverage.mean()).round(0)
        y_axis = "normalized_coverage"

    print_area_graph(
        dataframe,
        filepath,
        x_axis,
        y_axis,
        settings,
        ylim_height,
    )


def print_area_graph(dataframe, filepath, x_axis, y_axis, settings, ylim_height):
    """Print an area graph as PNG file. Used to print picture of coverage"""

    color = settings["color"]
    combine = settings["combine"]
    euploid = settings["euploid"]
    outd = settings["outd"]
    resolution = settings["dpi"]

    if not combine:  # Plot one chromosome per png
        is_printed = []
        for chrom_data in area_graph_generator(dataframe, x_axis, y_axis):
            fig, axis = plt.subplots(figsize=FIGSIZE_WIG)
            _common_settings(axis)
            axis.stackplot(chrom_data["x"], chrom_data["y"], colors=color)
            axis.set_ylim(bottom=0)
            fig.tight_layout()
            plt.ylim(0, ylim_height)
            plt.rcParams['figure.dpi'] = resolution
            plt.rcParams['savefig.dpi'] = resolution
            axis.set_xlim(0, CHROM_END_POS)  # bounds within maximum chromosome length
            outfile = outpath(outd, filepath, chrom_data["label"])
            print("outfile: {}".format(outfile))
            fig.savefig(
                outfile, transparent=True, bbox_inches="tight", pad_inches=0)
            is_printed.append(chrom_data["label"])
            plt.close(fig)  # save memory
        if euploid:
            print_transparent_pngs(filepath, outd, is_printed)
    else:
        print("WARNING: Combined area graphs are not implemented!")
        False


def print_bar_chart(dataframe, file_path, x_axis, y_axis, color, settings, ylim_height):
    """Print vertical bar chart"""
    combine = settings["combine"]
    euploid = settings["euploid"]
    outd = settings["outd"]
    resolution = settings["dpi"]
    is_printed = []
    for chrom_data in vertical_bar_generator(dataframe, x_axis, y_axis):
        fig, axis = plt.subplots(figsize=FIGSIZE_WIG)
        _common_settings(axis)
        axis.bar(
            chrom_data["x"],
            chrom_data["y"],
            width=chrom_data["bar_width"],
            color=color,
            linewidth=0,
        )
        plt.ylim(0, ylim_height)
        plt.rcParams['figure.dpi'] = resolution
        plt.rcParams['savefig.dpi'] = resolution
        axis.set_ylim(bottom=0)
        axis.set_xlim(0, CHROM_END_POS)  # bounds within maximum chromosome length
        fig.tight_layout()
        outfile = outpath(outd, file_path, chrom_data["label"])
        print("outfile: {}".format(outfile))
        fig.savefig(
            outfile, transparent=True, bbox_inches="tight", pad_inches=0)
        is_printed.append(chrom_data["label"])
        plt.close(fig)  # save memory
    if euploid:
        print_transparent_pngs(file_path, outd, is_printed)


def _plot_upd_regions(filepath, *args):
    """Print region as PNG file
    <chrom>  <start>  <stop>   <desc>
    where desc is
    [ORIGIN;TYPE;LOW_SIZE;INF_SITES;SNPS;HET_HOM;OPP_SITES;START_LOW;END_HIGH;HIGH_SIZE]
    """

    # Parse sites upd file to brokenbarcollection
    read_line = []
    settings = _args_to_dict(filepath, args)
    print(
        "Plot UPD REGIONS with settings \noutd:{}\neuploid: {}".format(
            settings["outd"], settings["euploid"]
        )
    )
    with open(filepath) as filepointer:
        for line in filepointer:
            if len(line.strip()) > 0:  # don't parse empty strings
                read_line.append(parse_upd_regions(line))
    region_list = [region_to_dict(i) for i in read_line]
    region_list_chr = compile_per_chrom(region_list)
    hbar_list = regions_to_hbar(region_list_chr)
    resolution = settings["dpi"]
    # Prepare canvas and plot
    fig = plt.figure(figsize=(10, 0.5))
    x_axis = fig.add_subplot(111)
    is_printed = []

    for bars in hbar_list:
        for bar in bars:
            x_axis.add_collection(bar)
            _common_settings(x_axis)
            x_axis.set_xlim(0, CHROM_END_POS)  # try to mimic nice bounds
            outfile = outpath(settings["outd"], filepath, bar.get_label())
            is_printed.append(bar.get_label())

        outfile = outpath(settings["outd"], filepath, bar.get_label())
        plt.rcParams['figure.dpi'] = resolution
        plt.rcParams['savefig.dpi'] = resolution
        fig.savefig(
            outfile, transparent=True, bbox_inches="tight", pad_inches=0)
        x_axis.cla()  # clear canvas before next iteration

    # print each name only once
    for name in dict.fromkeys(is_printed):
        print("outfile: {}".format(outpath(settings["outd"], filepath, name)))
    if settings["euploid"]:
        print_transparent_pngs(filepath, settings["outd"], is_printed)


def main():
    """Main function for Chromograph

    Parse incoming args and call correct function"""
    parser = ArgumentParser(
        epilog=(
            """\
         One OPERATION Command is needed for Chromograph to produce output

         """
        )
    )

    parser.add_argument(
        "-a",
        "--autozyg",
        dest="autozyg",
        help="Plot regions of autozygosity from bed file [OPERATION]",
        metavar="FILE",
    )
    parser.add_argument(
        "-c", "--coverage", dest="coverage_file", help=HELP_STR_COV + " [OPERATION]", metavar="FILE"
    )
    parser.add_argument(
        "-f",
        "--fracsnp",
        dest="hozysnp_file",
        help="Plot fraction of homozygous SNPs from wig file [OPERATION]",
        metavar="FILE",
    )
    parser.add_argument(
        "-i",
        "--ideogram",
        dest="ideofile",
        help=HELP_STR_IDEO.format(IDEOGRAM_FORMAT) + " [OPERATION]",
        metavar="FILE",
    )
    parser.add_argument(
        "-m", "--exom", dest="exom_coverage", help=HELP_STR_EXOM + " [OPERATION]", metavar="FILE"
    )
    parser.add_argument(
        "-r",
        "--regions",
        dest="upd_regions",
        help=HELP_STR_UPD_REGIONS + " [OPERATION]",
        metavar="FILE",
    )
    parser.add_argument(
        "-s",
        "--sites",
        dest="upd_sites",
        help=HELP_STR_UPD_SITE.format(UPD_FORMAT) + " [OPERATION]",
        metavar="FILE",
    )

    parser.add_argument("--step", type=int, help="fixed step size (default 5000)")
    parser.add_argument(
        "--version",
        help=HELP_STR_VSN.format(__version__),
        action="version",
        version="chromograph {}".format(__version__),
    )
    parser.add_argument("-d", "--outd", dest="outd", help="output dir", metavar="FILE")
    parser.add_argument("-e", "--euploid", help=HELP_STR_EU, action="store_true")
    parser.add_argument("-k", "--rgb", dest="rgb", help=HELP_STR_RGB, metavar="FILE")
    parser.add_argument("-n", "--norm", dest="norm", help=HELP_STR_NORM, action="store_true")
    parser.add_argument(
        "-u", "--chunk", type=int, help="Set Matplotlib.agg.path.chunksize (default 10000)"
    )
    parser.add_argument("-x", "--combine", help=HELP_STR_COMBINE, action="store_true")
    parser.add_argument("--small", action="store_true")
    parser.add_argument("--medium", action="store_true")
    parser.add_argument("--large", action="store_true")

    args = parser.parse_args()

    # Make command line and library interfaces behave identical regarding args
    args.norm = "norm" if args.norm else None
    args.combine = "combine" if args.combine else None
    args.euploid = "euploid" if args.euploid else None
    agg_chunks_size = args.chunk if args.chunk else DEFAULT_SETTING["agg_chunk_size"]
    matplotlib.rcParams["agg.path.chunksize"] = agg_chunks_size

    if args.autozyg:
        _plot_autozyg(args.autozyg, vars(args))
    if args.coverage_file:
        _plot_coverage_wig(args.coverage_file, vars(args))
    if args.exom_coverage:
        _plot_exom_coverage(args.exom_coverage, vars(args))
    if args.hozysnp_file:
        _plot_homosnp_wig(args.hozysnp_file, vars(args))
    if args.ideofile:
        _plot_ideogram(args.ideofile, vars(args))
    if args.upd_regions:
        _plot_upd_regions(args.upd_regions, vars(args))
    if args.upd_sites:
        _plot_upd_sites(args.upd_sites, vars(args))
    if len(sys.argv[1:]) == 0:
        parser.print_help()
        parser.exit()


if __name__ == "__main__":
    main()


def find_bad_apple(df, index):
    bad_apples = []
    previous_end = 0
    for i in range(len(df)):
        current_start = df["start"].iloc[i]
        if previous_end > current_start:
            # previous value is greater, this should not happen, something is wrong with the current frame
            bad_apples.append(df.iloc[i])
        previous_end = df["end"].iloc[i]
    return bad_apples
