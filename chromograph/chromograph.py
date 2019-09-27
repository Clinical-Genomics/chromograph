#!/usr/bin/env python

"""
Plot chromosoms and misc variants. Can be invoked from commandline
or from imported.

    $ ./chromograph.py --cyt cytoBand.bed

Further info:
  https://matplotlib.org/3.1.1/api/collections_api.html#matplotlib.collections.BrokenBarHCollection

"""

# TODO: instead of padding look-ahead and contsrict if overlap
# TODO: combined ROH image

from chromograph import __version__

import os
from argparse import ArgumentParser
from matplotlib import pyplot as plt
from matplotlib.collections import BrokenBarHCollection
import numpy as np
import pandas
import re
import sys
from .chr_utils import (read_cfg, filter_dataframe, png_filename,
                        outpath, parseWigDeclarationLine,
                        parse_updRegions)


PADDING = 200000
HEIGHT = 1
YBASE = 0
SPACE = 1
FIGSIZE = (6,8)
FIGSIZE_SINGLE = (8,8)
UPD_FORMAT = ['chrom', 'start', 'end', 'updType']
IDEOGRAM_FORMAT = ['chrom', 'start', 'end', 'name', 'gStain']
WIG_FORMAT = ['chrom', 'coverage', 'pos']
WIG_ORANGE = "#e89f00"


get_color = {
    # Cytoband colors
    'gneg': "#f7f7f7",
    'gpos25': "#666666",
    'gpos50': "#606060",
    'gpos75': "#2e2e2e",
    'gpos100': "#121212",
    'acen': "#b56666",
    'gvar': "#777777",
    'stalk': "#444444",

    # UPD sites colors
    'PB_HOMOZYGOUS': "#222222",
    'ANTI_UPD': "#555555",
    'PB_HETEROZYGOUS': "#888888",
    'UNINFORMATIVE': "#333333",
    'UPD_MATERNAL_ORIGIN': "#aa2200",     # Red
    'UPD_PATERNAL_ORIGIN': "#0044ff",     # Blue

    # UPD region colors
    'PATERNAL': "#0044ff",     # Blue
    'MATERNAL': "#aa2200"
}

def assure_dir(outd):
    """Create directory 'outd' if it does not exist"""
    print("outd: {}".format(outd))
    if not os.path.exists(outd):
        os.makedirs(outd)

def bed_collections_generatorCombine(df, y_positions, height,  **kwargs):
    """ Iterate dataframe

        Args:
            df(pandas dataframe)
            y_positions()
            height
        Yields:
            BrokenBarHCollection
    """
    for chrom, group in df.groupby('chrom'):
        print("chrom: {}".format(chrom))
        yrange = (y_positions[chrom], height)
        xranges = group[['start', 'width']].values
        yield BrokenBarHCollection(xranges,
                                   yrange,
                                   facecolors=group['colors'],
                                   label = chrom)


def bed_collections_generator(df, y_positions, height):
    """ Interate dataframe
    Yeilds:
    Brokenbarhcollection --from BED DF to be plotted
    """
    for chrom, group in df.groupby('chrom'):
        yrange = (0, height)
        xranges = group[['start', 'width']].values
        print("xranges: {}".format(xranges))
        print("yrange: {}".format(yrange))
        yield BrokenBarHCollection(
            xranges, yrange, facecolors=group['colors'], label =chrom)


def coverage_generator(df, data_state):
    """Iterate dataframe and yeild chromosome

    Args:
        df(dataframe)
        data_state('coverage'|'normalized_coverage')

    Yeilds:
        dict -- {'label', 'x', 'y'}
    """
    for chrom, group in df.groupby('chrom'):
        c = {'label': chrom,
             'x': group['pos'].values,
             'y': group[data_state].values }
        yield c


def coverage_generatorCombine(df, y_positions, height):
    """Iterate dataframe and yeild per chromosome, like coverage_generator()
    -with additional positional

    Args:
        df --
        y_positions --
        height ---

    Yeilds:
        BrokenBarhcollection
    """
    for chrom, group in df.groupby('chrom'):
        yrange = (0, height)
        xranges = group[['start', 'width']].values
        yield BrokenBarHCollection(
            xranges, yrange, facecolors=group['colors'], label =chrom)


def print_settings(ax):
        ax.get_xaxis().set_visible(False)
        ax.get_yaxis().set_visible(False)
        ax.set_axis_off()    # Remove black line surrounding pic.


def print_individual_pics(df, chrom_ybase, chrom_centers, infile, outd):
    """Print one chromosomes per image file"""
    fig = plt.figure(figsize=(10, .5))
    ax = fig.add_subplot(111)

    for collection in bed_collections_generator(df, chrom_ybase, HEIGHT):
        ax.add_collection(collection)
        print_settings(ax)
        ax.set_xlim((-12159968, 255359341))      # try to mimic nice bounds

        outfile = outpath(outd, infile, collection.get_label() )

        fig.savefig(outfile, transparent = True, bbox_inches='tight', pad_inches=0)
        ax.cla()             # clear canvas before next iteration


def print_combined_pic(df, chrom_ybase, chrom_centers, infile, outd, chr_list):
    """Print all chromosomes in a single PNG picture"""
    fig = plt.figure(figsize=FIGSIZE)
    ax = fig.add_subplot(111)
    for c in bed_collections_generatorCombine(df, chrom_ybase, HEIGHT):
        ax.add_collection(c)

    ax.set_yticks([chrom_centers[i] for i in chr_list])
    ax.set_yticklabels(chr_list)
    ax.axis('tight')
    outfile = outpath(outd, infile, 'combined')
    fig.savefig(outfile, transparent = True, bbox_inches='tight', pad_inches=0)


def bed_to_dataframe(file, spec):
    """Read a bed file into a Pandas dataframe according to 'spec' """
    return pandas.read_csv(file, names=spec, sep ='\t', skiprows=1)


def wig_to_dataframe(infile, step, format):
    """Read a wig file into a Pandas dataframe

    infile(str): Path to file

    Returns:
        Dataframe

    """
    fs = open(infile, 'r')
    coverage_data = []
    pos = 0
    chr = ""
    for line in fs.readlines():
        try:
            f = float(line)
            coverage_data.append([chr, f, pos])
            pos += 5000
        except ValueError:
            reresult = re.search("chrom=(\w*)", line) # find chromosome name in line
            if reresult:
                last_pos = [chr, 0, 249255001] # writen in every set to give same scale when plotting
                coverage_data.append(last_pos)
                chr = reresult.group(1) # start working on next chromosome
                pos =0
    fs.close()
    df = pandas.DataFrame(coverage_data, columns= format)
    return df


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
        chrom_centers[chrom] = ybase + HEIGHT / 2.
        ybase += HEIGHT + SPACE
    return chrom_ybase, chrom_centers


def plot_ideogram(file, *args, **kwargs):
    """Visualize chromosome ideograms from bed-file. Format:

    Args:
        file(string path)

    Optional Args:
        combine -- output all graphs in one png
        outd=<str> -- output directory

    Returns:
          None
    """
    cfg = read_cfg()
    outd = os.path.dirname(file)
    combine = False
    if 'combine' in args:
        combine = True
    if 'outd' in kwargs and kwargs['outd'] is not None:
        outd = kwargs['outd']
        assure_dir(outd)

    print("Plot ideograms with settings\ncombine:{}\noutd:{}".format(combine, outd))
    chromosome_list = cfg['chromosome_str']
    df = bed_to_dataframe(file, IDEOGRAM_FORMAT)
    df = filter_dataframe(df, chromosome_list)      # delete chromosomes not in CHROMOSOME_LIST
    df['width'] = df.end - df.start
    df['colors'] = df['gStain'].apply(lambda x: get_color[x])
    chrom_ybase, chrom_centers = graph_coordinates(chromosome_list)
    if combine:
        print_combined_pic(df, chrom_ybase, chrom_centers, file, outd, chromosome_list)
    else:
        print_individual_pics(df, chrom_ybase, chrom_centers, file, outd)


def plot_upd(file, *args, **kwargs):
    """Visualize UPD data from bed-file. Bed format as:

        Chromosome <tab> Start <tab> End <tab> Upd-type

    These can be generated with SV caller upd.py. It can be found at
    [https://github.com/bjhall/upd]

    Args:
        file<str> -- input file on wig format

    Optional Args:
        combine -- output all graphs in one png
        normalize -- normalize to mean
        outd=<str> -- output directory
    Returns: None

    """
    cfg = read_cfg()
    outd = os.path.dirname(file)
    combine = False
    if 'combine' in args:
        combine = True
    if 'outd' in kwargs and kwargs['outd'] is not None:
        outd = kwargs['outd']
        assure_dir(outd)

    print("Plot UPD with settings\ncombine:{}".format(combine))
    df = bed_to_dataframe(file, UPD_FORMAT)
    df.chrom = df.chrom.astype(str)  # Explicitly set chrom to string (read as int)
    chromosome_list = cfg['chromosome_int']
    df = filter_dataframe(df, chromosome_list)   # delete chromosomes not in CHROMOSOME_LIST_UPD
    df['width'] = (df.end-df.start) + PADDING
    df['colors'] = df['updType'].apply(lambda x: get_color[x])
    chrom_ybase, chrom_centers = graph_coordinates(chromosome_list)
    if combine:
        print_combined_pic(df, chrom_ybase, chrom_centers, file, outd, chromosome_list)
    else:
        print_individual_pics(df, chrom_ybase, chrom_centers, file, outd)


def plot_wig(file, *args, **kwargs):
    """Outputs png:s of data given on WIG format

    Args:
        file(str)

    Optional Args:
        combine -- output all graphs in one png
        normalize -- normalize to mean
        outd(str) -- output directory
    Returns: None

    """
    cfg = read_cfg()
    decl = parseWigDeclarationLine(file, ' ')
    outd = os.path.dirname(file)
    combine = False
    fixedStep = decl['step'] #cfg['wig_step']
    normalize = False
    color = WIG_ORANGE          # set default color, override if rgb in kwargs
    if 'combine' in args:
        combine = True
    if 'normalize' in args:
        normalize = True
    if 'rgb' in kwargs and kwargs['rgb'] is not None:
        color = toRGB(kwargs['rgb'])
    if 'outd' in kwargs and kwargs['outd'] is not None:
        print("outd?")
        outd = kwargs['outd']
        assure_dir(outd)
    if 'step' in kwargs and kwargs['step'] is not None:
        fixedStep = kwargs['step']

    print("Plot WIG with settings \nstep: {}\noutd:{}\ncombine:{}\nnormalize:{}"
          .format(fixedStep, outd, combine, normalize))

    chromosome_list = listType(decl['chrom'], cfg)
    df = wig_to_dataframe(file, fixedStep, WIG_FORMAT)
    df = filter_dataframe(df, chromosome_list)   # delete chromosomes not in CHROMOSOME_LIST
    df['normalized_coverage']=(df.coverage /df.coverage.mean()).round(0)
    print_wig(df, file, outd, combine, normalize, color)


def print_wig(df, file, outd, combine, normalize, color):
    data_state = 'normalized_coverage' if normalize else 'coverage'
    if not combine:           # Plot one chromosome per png
        for c in coverage_generator(df, data_state):
            fig, ax = plt.subplots(figsize=(8, .7))
            fig.max_open_warning = 28
            print_settings(ax)
            ax.stackplot(c['x'], c['y'], colors=color)
            plt.ylim(0,5)
            ax.set_ylim(bottom=0)
            ax.set_xlim((0, 255359341))      # try to mimic nice bounds
            fig.tight_layout()
            outfile = outpath(outd, file, c['label'] )
            fig.savefig(outfile, transparent = True, bbox_inches='tight', pad_inches=0)
            ax.cla()              # clear axis before next iteration
            fig.clf()             # clear figure before next iteration
    else:
        # TODO:
        print("Combined WIG png not implemented!")
        False


def plot_regions(file, *args, **kwargs):
    """  """

    # Parse sites upd file to brokenbarcollection
    l = []
    outd = os.path.dirname(file)
    if 'outd' in kwargs and kwargs['outd'] is not None:
        outd = kwargs['outd']
        assure_dir(outd)
    print("Plot UPD REGIONS with settings \noutd:{}".format(outd))
    with open(file) as fp:
        for line in fp:
            l.append(parse_updRegions(line, '\t'))
    bb = [sitesBrokenBar(i) for i in l]

    # Prepare canvas and plot
    fig = plt.figure(figsize=(10, .5))
    ax = fig.add_subplot(111)
    for collection in bb:
        ax.add_collection(collection)
        print_settings(ax)
        ax.set_xlim((-12159968, 255359341))      # try to mimic nice bounds
        outfile = outpath(outd, file, collection.get_label() )
        fig.savefig(outfile, transparent = False, bbox_inches='tight', pad_inches=0)
        ax.cla()             # clear canvas before next iteration


def sitesBrokenBar(region):
    """ Make a MathPlotLIb 'BrokenbarCollection' from upd sites data"""
    start = int(region['start'])
    width = int(region['stop']) - int(region['start'])
    color = get_color[ region['desc']['origin'] ]
    xranges = [[start, width]]
    yrange = (0, 1)
    return BrokenBarHCollection(xranges,
                                yrange,
                                facecolors= color,
                                label = region['chr'])


def toRGB(color):
    x, *xs = str(color)
    if x is '#':
        return color            # color was alread "#123456"
    else:
        return '#'+ str(color)


def listType(chr_type, cfg):
    if chr_type == 'int':
        return cfg['chromosome_int']
    else:
        return cfg['chromosome_str']


def main():
    parser = ArgumentParser()
    parser.add_argument("-u", "--upd", dest="updfile",
                        help="input UPD sites file on format {}".format(UPD_FORMAT),
                        metavar="FILE")
    parser.add_argument("-g", "--regions", dest="regionsfile",
                        help="input UPD regions file",
                        metavar="FILE")
    parser.add_argument("-e", "--ideo", dest="ideofile",
                        help="input ideogram (bed-file) on format {}".format(IDEOGRAM_FORMAT),
                        metavar="FILE")
    parser.add_argument("-w", "--coverage", dest="wigfile",
                        help="input fixed step wig-file",
                        metavar="FILE")
    parser.add_argument("-o", "--outd", dest="outd",
                        help="output dir",
                        metavar="FILE")
    parser.add_argument("-r", "--rgb", dest="rgb",
                        help="graph color in RGB hex (only in combination with --coverage)",
                        metavar="FILE")
    parser.add_argument("--step", type=int, help="fixed step size (default 5000)")
    parser.add_argument("-c", "--combine",
                        help="plot all graphs in one file, default one graph per file",
                        action='store_true')
    parser.add_argument("--version",
                        help="Display program version ({}) and exit.".format(__version__),
                        action='version', version="chromograph {}".format(__version__))

    args = parser.parse_args()
    if args.ideofile:
        plot_ideogram(args.ideofile, args.combine, outd = args.outd)
    if args.updfile:
        plot_upd(args.updfile, args.combine, outd = args.outd, step=args.step)
    if args.wigfile:
        plot_wig(args.wigfile, args.combine, outd = args.outd, step=args.step, rgb=args.rgb)
    if args.regionsfile:
        plot_regions(args.regionsfile, outd = args.outd)
    if len(sys.argv[1:])==0:
        parser.print_help()
        # parser.print_usage() # for just the usage line
        parser.exit()


if __name__ == "__main__":
    main()
