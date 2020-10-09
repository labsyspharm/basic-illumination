# @File(label="Select a slide to process") filename
# @File(label="Select the output location", style="directory") output_dir
# @String(label="Experiment name (base name for output files)") experiment_name
# @Float(label="Flat field smoothing parameter (0 for automatic)", value=0.1) lambda_flat
# @Float(label="Dark field smoothing parameter (0 for automatic)", value=0.01) lambda_dark

# Takes a slide (or other multi-series BioFormats-compatible file set) and
# generates flat- and dark-field correction profile images with BaSiC. The
# output format is two multi-series TIFF files (one for flat and one for dark)
# which is the input format used by Ashlar.

# Invocation for running from the commandline:
#
# ImageJ --ij2 --headless --run imagej_basic_ashlar.py "filename='input.ext',output_dir='output',experiment_name='my_experiment'"

import sys
from ij import IJ, WindowManager, Prefs
from ij.macro import Interpreter
from loci.plugins import BF
from loci.plugins.in import ImporterOptions
from loci.formats import ImageReader
from loci.formats.in import DynamicMetadataOptions
import BaSiC_ as Basic

import pdb


def main():

    Interpreter.batchMode = True

    if (lambda_flat == 0) ^ (lambda_dark == 0):
        print ("ERROR: Both of lambda_flat and lambda_dark must be zero,"
               " or both non-zero.")
        return
    lambda_estimate = "Automatic" if lambda_flat == 0 else "Manual"

    print "Loading images..."

    # For multi-scene .CZI files, we need raw tiles instead of the
    # auto-stitched mosaic and we don't want labels or overview images.  This
    # only affects BF.openImagePlus, not direct use of the BioFormats reader
    # classes which we also do (see below)
    Prefs.set("bioformats.zeissczi.allow.autostitch",  "false")
    Prefs.set("bioformats.zeissczi.include.attachments", "false")

    # Use BioFormats reader directly to determine dataset dimensions without
    # reading every single image. The series count (num_images) is the one value
    # we can't easily get any other way, but we might as well grab the others
    # while we have the reader available.
    dyn_options = DynamicMetadataOptions()
    # Directly calling a BioFormats reader will not use the IJ Prefs settings
    # so we need to pass these options explicitly.
    dyn_options.setBoolean("zeissczi.autostitch", False)
    dyn_options.setBoolean("zeissczi.attachments", False)
    bfreader = ImageReader()
    bfreader.setMetadataOptions(dyn_options)
    bfreader.id = str(filename)
    num_images = bfreader.seriesCount
    num_channels = bfreader.sizeC
    width = bfreader.sizeX
    height = bfreader.sizeY
    bfreader.close()

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

        options = ImporterOptions()
        options.id = str(filename)
        options.setOpenAllSeries(True)
        # concatenate=True gives us a single stack rather than a list of
        # separate images.
        options.setConcatenate(True)
        # Limit the reader to the channel we're currently working on. This loop
        # is mainly why we need to know num_images before opening anything.
        for i in range(num_images):
            options.setCBegin(i, channel)
            options.setCEnd(i, channel)
        # openImagePlus returns a list of images, but we expect just one (a
        # stack).
        input_image = BF.openImagePlus(options)[0]

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
