# @String(label="Enter a filename pattern describing the TIFFs to process") pattern
# @File(label="Select the output location", style="directory") output_dir
# @String(label="Experiment name (base name for output files)") experiment_name
# @Float(label="Flat field smoothing parameter (0 for automatic)", value=0.1) lambda_flat
# @Float(label="Dark field smoothing parameter (0 for automatic)", value=0.01) lambda_dark

import sys
import os
import re
import collections
from ij import IJ, WindowManager, ImagePlus, ImageStack
from ij.io import Opener
from ij.macro import Interpreter
import BaSiC_ as Basic


def enumerate_filenames(pattern):
    """Return filenames matching pattern (a str.format pattern containing
    {channel} and {tile} placeholders).

    Returns a list of lists, where the top level is indexed by channel number
    and the bottom level is sorted filenames for that channel.

    """
    (base, pattern) = os.path.split(pattern)
    regex = re.sub(r'{([^:}]+)(?:[^}]*)}', r'(?P<\1>.*?)',
                   pattern.replace('.', '\.'))
    tiles = set()
    channels = set()
    num_images = 0
    # Dict[channel: int, List[filename: str]]
    filenames = collections.defaultdict(list)
    for f in os.listdir(base):
        match = re.match(regex, f)
        if match:
            gd = match.groupdict()
            tile = int(gd['tile'])
            channel = int(gd['channel'])
            tiles.add(tile)
            channels.add(channel)
            filenames[channel].append(os.path.join(base, f))
            num_images += 1
    if len(tiles) * len(channels) != num_images:
        raise Exception("Missing some image files")
    filenames = [
        sorted(filenames[channel])
        for channel in sorted(filenames.keys())
    ]
    return filenames


def main():

    Interpreter.batchMode = True

    if (lambda_flat == 0) ^ (lambda_dark == 0):
        print ("ERROR: Both of lambda_flat and lambda_dark must be zero,"
               " or both non-zero.")
        return
    lambda_estimate = "Automatic" if lambda_flat == 0 else "Manual"

    #import pdb; pdb.set_trace()
    print "Loading images..."
    filenames = enumerate_filenames(pattern)
    num_channels = len(filenames)
    num_images = len(filenames[0])
    image = Opener().openImage(filenames[0][0])
    width = image.width
    height = image.height
    image.close()

    # The internal initialization of the BaSiC code fails when we invoke it via
    # scripting, unless we explicitly set a the private 'noOfSlices' field.
    # Since it's private, we need to use Java reflection to access it.
    Basic_noOfSlices = Basic.getDeclaredField('noOfSlices')
    Basic_noOfSlices.setAccessible(True)
    basic = Basic()
    Basic_noOfSlices.setInt(basic, num_images)

    # Pre-allocate the output profile images, since we have all the dimensions.
    ff_image = IJ.createImage("Flat-field", width, height, num_channels, 32);
    df_image = IJ.createImage("Dark-field", width, height, num_channels, 32);

    print("\n\n")

    # BaSiC works on one channel at a time, so we only read the images from one
    # channel at a time to limit memory usage.
    for channel in range(num_channels):
        print "Processing channel %d/%d..." % (channel + 1, num_channels)
        print "==========================="

        stack = ImageStack(width, height, num_images)
        opener = Opener()
        for i, filename in enumerate(filenames[channel]):
            print "Loading image %d/%d" % (i + 1, num_images)
            image = opener.openImage(filename)
            stack.setProcessor(image.getProcessor(), i + 1)
        input_image = ImagePlus("input", stack)

        # BaSiC seems to require the input image is actually the ImageJ
        # "current" image, otherwise it prints an error and aborts.
        WindowManager.setTempCurrentImage(input_image)
        basic.exec(
            input_image, None, None,
            "Estimate shading profiles", "Estimate both flat-field and dark-field",
            lambda_estimate, lambda_flat, lambda_dark,
            "Ignore", "Compute shading only"
        )
        input_image.close()

        # Copy the pixels from the BaSiC-generated profile images to the
        # corresponding channel of our output images.
        ff_channel = WindowManager.getImage("Flat-field:%s" % input_image.title)
        ff_image.slice = channel + 1
        ff_image.getProcessor().insert(ff_channel.getProcessor(), 0, 0)
        ff_channel.close()
        df_channel = WindowManager.getImage("Dark-field:%s" % input_image.title)
        df_image.slice = channel + 1
        df_image.getProcessor().insert(df_channel.getProcessor(), 0, 0)
        df_channel.close()

        print("\n\n")

    template = '%s/%s-%%s.tif' % (output_dir, experiment_name)
    ff_filename = template % 'ffp'
    IJ.saveAsTiff(ff_image, ff_filename)
    ff_image.close()
    df_filename = template % 'dfp'
    IJ.saveAsTiff(df_image, df_filename)
    df_image.close()

    print "Done!"


main()
