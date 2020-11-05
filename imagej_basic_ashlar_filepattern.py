# @String(label="Enter a filename pattern describing the TIFFs to process") pattern
# @File(label="Select the output location", style="directory") output_dir
# @String(label="Experiment name (base name for output files)") experiment_name
# @Float(label="Flat field smoothing parameter (0 for automatic)", value=0.1) lambda_flat
# @Float(label="Dark field smoothing parameter (0 for automatic)", value=0.01) lambda_dark

# Takes a filename pattern describing a list of image files and generates flat-
# and dark-field correction profile images with BaSiC. The pattern must contain
# a "*" wildcard to indicate the part of the filename that varies with the image
# series number. If the images are stored with one channel per file then the
# pattern must also contain the placeholder {channel} in place of the channel
# name or number. If the image files are multi-channel then the {channel}
# placeholder must be omitted. The output format is two multi-channel TIFF files
# (one for flat and one for dark) which is the input format used by Ashlar.

# Invocation for running from the commandline:
# (to match files like "s001_c1.tif", "s001_c2.tif", "s002_c1.tif", etc.)
#
# ImageJ --ij2 --headless --run imagej_basic_ashlar_filepattern.py "pattern='input/s*_c{channel}.tif',output_dir='output',experiment_name='my_experiment'"

import sys
import os
import re
import collections
from ij import IJ, WindowManager, ImagePlus, ImageStack
from ij.io import Opener
from ij.macro import Interpreter
import BaSiC_ as Basic


def enumerate_filenames(pattern):
    """Return filenames matching pattern (a glob pattern containing an optional
    {channel} placeholder).

    Returns a list of lists, where the top level is indexed by sorted channel
    name/number and the bottom level is filenames for that channel.

    """
    (base, pattern) = os.path.split(pattern)
    regex = re.sub(r'{([^:}]+)(?:[^}]*)}', r'(?P<\1>.*?)',
                   pattern.replace('.', '\.').replace('*', '.*?'))
    channels = set()
    num_images = 0
    # Dict[Union[int, str, None], List[str]]
    filenames = collections.defaultdict(list)
    for f in os.listdir(base):
        match = re.match(regex, f)
        if match:
            gd = match.groupdict()
            channel = gd.get('channel', None)
            try:
                channel = int(channel)
            except (ValueError, TypeError):
                pass
            channels.add(channel)
            filenames[channel].append(os.path.join(base, f))
            num_images += 1
    if num_images % len(channels) != 0:
        print (
            "ERROR: Some image files seem to be missing --"
            " image count (%d) is not a multiple of channel count (%d)"
            % (num_images, len(channels))
        )
        return []
    channels = sorted(channels)
    if len(channels) > 1:
        print("Detected the following channel names/numbers from filenames:")
        for channel in channels:
            print("    %s" % channel)
    filenames = [filenames[channel] for channel in channels]
    return filenames


def main():

    Interpreter.batchMode = True

    if (lambda_flat == 0) ^ (lambda_dark == 0):
        print ("ERROR: Both of lambda_flat and lambda_dark must be zero,"
               " or both non-zero.")
        return
    lambda_estimate = "Automatic" if lambda_flat == 0 else "Manual"

    print "Loading images..."
    filenames = enumerate_filenames(pattern)
    if len(filenames) == 0:
        return
    # This is the number of channels inferred from the filenames. The number
    # of channels in an individual image file will be determined below.
    num_channels = len(filenames)
    num_images = len(filenames[0])
    image = Opener().openImage(filenames[0][0])
    if image.getNDimensions() > 3:
        print "ERROR: Can't handle images with more than 3 dimensions."
    (width, height, channels, slices, frames) = image.getDimensions()
    # The third dimension could be any of these three, but the other two are
    # guaranteed to be equal to 1 since we know NDimensions is <= 3.
    image_channels = max((channels, slices, frames))
    image.close()
    if num_channels > 1 and image_channels > 1:
        print (
            "ERROR: Can only handle single-channel images with {channel} in"
            " the pattern, or multi-channel images without {channel}. The"
            " filename patterns imply %d channels and the images themselves"
            " have %d channels." % (num_channels, image_channels)
        )
        return
    if image_channels == 1:
        multi_channel = False
    else:
        print (
            "Detected multi-channel image files with %d channels"
            % image_channels
        )
        multi_channel = True
        num_channels = image_channels
        # Clone the filename list across all channels. We will handle reading
        # the individual image planes for each channel below.
        filenames = filenames * num_channels

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
            # For multi-channel images the channel determines the plane to read.
            args = [channel + 1] if multi_channel else []
            image = opener.openImage(filename, *args)
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
