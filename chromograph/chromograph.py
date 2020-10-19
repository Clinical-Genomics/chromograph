"""
Plot chromosoms and misc variants. Can be invoked from commandline
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
import pandas
import matplotlib
from matplotlib import pyplot as plt
from matplotlib.collections import BrokenBarHCollection
from chromograph import __version__
from .chr_utils import (read_cfg, filter_dataframe,
                        outpath, parse_wig_declaration,
                        parse_upd_regions)

matplotlib.use('Agg')

# TODO: instead of padding look-ahead and contsrict if overlap
# TODO: combined ROH image


PADDING = 200000
COVERAGE_END = 249255000        # write all coverage files to the same size canvas
HEIGHT = 1
YBASE = 0
SPACE = 1
FIGSIZE = (6, 8)
FIGSIZE_SINGLE = (8, 8)
UPD_FORMAT = ['chrom', 'start', 'end', 'updType']
IDEOGRAM_FORMAT = ['chrom', 'start', 'end', 'name', 'gStain']
WIG_FORMAT = ['chrom', 'coverage', 'pos']
WIG_ORANGE = "#e89f00"
WIG_MAX = 70.0
PNG_BYTES=b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x01\x00\x00\x00\x007n\xf9$\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01H\xaf\xa4q\x00\x00\x00\x00IEND\xaeB`\x82'
CHROMOSOMES=['chr1', 'chr2', 'chr3', 'chr4', 'chr5', 'chr6', 'chr7',
             'chr8', 'chr9', 'chr10', 'chr11', 'chr12', 'chr13',
             'chr14', 'chr15', 'chr16', 'chr17', 'chr18', 'chr19',
             'chr20', 'chr21', 'chr22', 'chrM', 'chrX', 'chrY']



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

def bed_collections_generator_combine(df, y_positions, height):
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
                                   label=chrom)


def bed_collections_generator(df, height):
    """ Interate dataframe
    Yeilds:
    Brokenbarhcollection --from BED DF to be plotted
    """
    for chrom, group in df.groupby('chrom'):
        yrange = (0, height)
        xranges = group[['start', 'width']].values
        yield BrokenBarHCollection(
            xranges, yrange, facecolors=group['colors'], label=chrom)


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
             'y': group[data_state].values}
        yield c


def coverage_generator_combine(df, height):
    """Iterate dataframe and yeild per chromosome, like coverage_generator()
    -with additional positional

    Args:
        df --
        height ---

    Yeilds:
        BrokenBarhcollection
    """
    for chrom, group in df.groupby('chrom'):
        yrange = (0, height)
        xranges = group[['start', 'width']].values
        yield BrokenBarHCollection(
            xranges, yrange, facecolors=group['colors'], label=chrom)


def common_settings(ax):
    """Common Matplotlib settings"""
    ax.get_xaxis().set_visible(False)
    ax.get_yaxis().set_visible(False)
    ax.set_axis_off()    # Remove black line surrounding pic.


def print_individual_pics(df, infile, outd, euploid):
    """Print one chromosomes per image file"""
    fig = plt.figure(figsize=(10, .5))
    ax = fig.add_subplot(111)
    plt.rcParams.update({'figure.max_open_warning': 0})
    if euploid:
        print_empty_pngs(file, outd)

    for collection in bed_collections_generator(df, HEIGHT):
        ax.add_collection(collection)
        common_settings(ax)
        ax.set_xlim((-12159968, 255359341))      # try to mimic nice bounds
        outfile = outpath(outd, infile, collection.get_label())
        print("outfile: {}".format(outfile))
        fig.savefig(outfile, transparent=True, bbox_inches='tight', pad_inches=0)
        ax.cla()             # clear canvas before next iteration


def print_combined_pic(df, chrom_ybase, chrom_centers, infile, outd, chr_list):
    """Print all chromosomes in a single PNG picture"""
    fig = plt.figure(figsize=FIGSIZE)
    ax = fig.add_subplot(111)
    for c in bed_collections_generator_combine(df, chrom_ybase, HEIGHT):
        ax.add_collection(c)

    ax.set_yticks([chrom_centers[i] for i in chr_list])
    ax.set_yticklabels(chr_list)
    ax.axis('tight')
    outfile = outpath(outd, infile, 'combined')
    print("outfile: {}".format(outfile))
    fig.savefig(outfile, transparent=True, bbox_inches='tight', pad_inches=0)


def print_empty_pngs(file, outd):
    """Write an empty png file to disk for every chromosome, always including Y.
    Motivated by auxilary software not being able to handle missing output
    chromosome are missing in the wig."""
    for chr in CHROMOSOMES:
        outfile = outpath(outd, file, chr)
        f = open(outfile, "bw")
        f.write(PNG_BYTES)
        f.close()


def bed_to_dataframe(file, spec):
    """Read a bed file into a Pandas dataframe according to 'spec' """
    return pandas.read_csv(file, names=spec, sep='\t', skiprows=1)


def wig_to_dataframe(infile, step, col_format):
    """Read a wig file into a Pandas dataframe

    infile(str): Path to file

    Returns:
        Dataframe

    """
    fs = open(infile, 'r')
    coverage_data = []
    pos = 0
    chrom = ""
    for line in fs.readlines():
        try:
            f = float(line)
            f = f if f < WIG_MAX else WIG_MAX
            coverage_data.append([chrom, f, pos])
            pos += step
        except ValueError:
            reresult = re.search("chrom=(\w*)", line) # find chromosome name in line
            if reresult:
                print(line)
                start_pos = [chrom, 0, 1] # write 0 in beginning, works against bug
                stop_pos = [chrom, 0, pos + 1] # write 0 at end removes linear slope
                last_pos = [chrom, 0, COVERAGE_END] # write trailing char for scale when plotting
#               coverage_data.insert(start_pos)
                coverage_data.append(stop_pos)
                coverage_data.append(last_pos)
                chrom = reresult.group(1) # start working on next chromosome
                pos = 0
    fs.close()
    df = pandas.DataFrame(coverage_data, columns=col_format)
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

    # try two different chromosome formats, if both result in
    # an empty dataframe, raise IdeoParseError
    for setting in ['chromosome_str', 'chromosome_int']:
        chromosome_list = cfg[setting]
        df = bed_to_dataframe(file, IDEOGRAM_FORMAT)
        # delete chromosomes not in CHROMOSOME_LIST
        df = filter_dataframe(df, chromosome_list)
        if df.size > 0:
            break
    if df.size == 0:
        raise Exception('Ideogram parsing')
    df['width'] = df.end - df.start
    df['colors'] = df['gStain'].apply(lambda x: get_color[x])
    chrom_ybase, chrom_centers = graph_coordinates(chromosome_list)
    if combine:
        print_combined_pic(df, chrom_ybase, chrom_centers, file, outd, chromosome_list)
    else:
        print_individual_pics(df, file, outd, euploid)


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
    euploid = False
    if 'combine' in args:
        combine = True
    if 'outd' in kwargs and kwargs['outd'] is not None:
        outd = kwargs['outd']
        assure_dir(outd)

    print("Plot UPD with settings\ncombine:{}\neuploid:{}".format(combine, euploid))
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
        print_individual_pics(df, file, outd, euploid)


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
    decl = parse_wig_declaration(file, ' ')
    outd = os.path.dirname(file)
    combine = False
    fixedStep = decl['step'] #cfg['wig_step']
    normalize = False
    euploid = False
    color = WIG_ORANGE          # set default color, override if rgb in kwargs

    if 'combine' in args:
        combine = True
    if 'norm' in args:
        normalize = True
    if 'euploid' in args:
        euploid = True
    if 'rgb' in kwargs and kwargs['rgb'] is not None:
        color = rgb_str(kwargs['rgb'])
    if 'outd' in kwargs and kwargs['outd'] is not None:
        print("outd?")
        outd = kwargs['outd']
        assure_dir(outd)
    if 'step' in kwargs and kwargs['step'] is not None:
        fixedStep = kwargs['step']
    print("Plot WIG with settings \nstep: {}\noutd:{}\ncombine:{}\nnormalize:{}\neuploid:{}"
          .format(fixedStep, outd, combine, normalize, euploid))

    chromosome_list = list_type(decl['chrom'], cfg)
    df = wig_to_dataframe(file, fixedStep, WIG_FORMAT)
    df = filter_dataframe(df, chromosome_list)   # delete chromosomes not in CHROMOSOME_LIST
    df['normalized_coverage'] = (df.coverage /df.coverage.mean()).round(0)
    print_wig(df, file, outd, combine, normalize, color, euploid)


def print_wig(df, file, outd, combine, normalize, color, euploid):
    """Print wig graph as PNG file"""
    data_state = 'normalized_coverage' if normalize else 'coverage'
    if not combine:           # Plot one chromosome per png
        if euploid:
            print_empty_pngs(file, outd)
        for c in coverage_generator(df, data_state):
            fig, ax = plt.subplots(figsize=(8, .7))
            common_settings(ax)
            ax.stackplot(c['x'], c['y'], colors=color)
            plt.ylim(0, 5)
            ax.set_ylim(bottom=0)
            ax.set_xlim((0, 255359341))      # try to mimic nice bounds
            fig.tight_layout()
            outfile = outpath(outd, file, c['label'])
            print("outfile: {}".format(outfile))
            fig.savefig(outfile, transparent=True, bbox_inches='tight', pad_inches=0)
            plt.close(fig)                   # save memory
    else:
        # TODO:
        print("WARNING: Combined WIG png not implemented!")
        False


def plot_regions(file, *args, **kwargs):
    """  Print region as PNG file"""

    # Parse sites upd file to brokenbarcollection
    l = []
    outd = os.path.dirname(file)
    euploid = False
    if 'euploid' in args:
        euploid = True
    if 'outd' in kwargs and kwargs['outd'] is not None:
        outd = kwargs['outd']
        assure_dir(outd)
    print("Plot UPD REGIONS with settings \noutd:{}\neuploid: {}".format(outd, euploid))
    with open(file) as fp:
        for line in fp:
            l.append(parse_upd_regions(line))
    bb = [sites_to_brokenbar(i) for i in l]

    if euploid:
        print_empty_pngs(file, outd)

    # Prepare canvas and plot
    fig = plt.figure(figsize=(10, .5))
    ax = fig.add_subplot(111)
    for collection in bb:
        ax.add_collection(collection)
        common_settings(ax)
        ax.set_xlim((-12159968, 255359341))      # try to mimic nice bounds
        outfile = outpath(outd, file, collection.get_label())
        print("outfile: {}".format(outfile))
        fig.savefig(outfile, transparent=False, bbox_inches='tight', pad_inches=0)
        ax.cla()             # clear canvas before next iteration


def sites_to_brokenbar(region):
    """ Make a MathPlotLIb 'BrokenbarCollection' from upd sites data"""
    start = int(region['start'])
    width = int(region['stop']) - int(region['start'])
    color = get_color[region['desc']['origin']]
    xranges = [[start, width]]
    yrange = (0, 1)
    return BrokenBarHCollection(xranges,
                                yrange,
                                facecolors=color,
                                label=region['chr'])


def rgb_str(color):
    """Return #color"""
    head, *tail = str(color)
    if head == '#':
        return color            # color was alread on format "#123456"
    else:
        return '#'+ str(color)


def list_type(chr_type, cfg):
    """ Determine type annd return list of possible
    field names in parsed data frame"""
    if chr_type == 'int':
        return cfg['chromosome_int']
    else:
        return cfg['chromosome_str']


def main():
    """Main function for Chromograph

    Parse incoming args and call correct function"""
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
    parser.add_argument("-n", "--norm", dest="norm",
                        help="normalize data (only used for wig/coverage)",
                        action='store_true')
    parser.add_argument("--step", type=int, help="fixed step size (default 5000)")
    parser.add_argument("-c", "--combine",
                        help="plot all graphs in one file, default one graph per file",
                        action='store_true')
    parser.add_argument("--version",
                        help="Display program version ({}) and exit.".format(__version__),
                        action='version', version="chromograph {}".format(__version__))
    parser.add_argument("-p", "--euploid",
                        help="always output an euploid amount of files -some may be empty PNGs",
                        action='store_true')

    args = parser.parse_args()


    # Make command line and library interfaces behave identical regarding args
    args.norm = 'norm' if args.norm else None
    args.combine = 'combine' if args.combine else None
    args.euploid = 'euploid' if args.euploid else None

    if args.ideofile:
        plot_ideogram(args.ideofile, args.combine, outd=args.outd)
    if args.updfile:
        plot_upd(args.updfile, args.combine, args.euploid, outd=args.outd, step=args.step)
    if args.wigfile:
        plot_wig(args.wigfile, args.combine, args.norm, args.euploid, outd=args.outd, step=args.step, rgb=args.rgb)
    if args.regionsfile:
        plot_regions(args.regionsfile, args.euploid, outd=args.outd)
    if len(sys.argv[1:]) == 0:
        parser.print_help()
        # parser.print_usage() # for just the usage line
        parser.exit()


if __name__ == "__main__":
    main()
