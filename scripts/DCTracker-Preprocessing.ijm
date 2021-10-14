/*
 * DCTracker Pre-processing pipeline 
 * Author: Samuel Prince and Kamelia Maguemoun 
 * Parts of this pipeline are inspired by some scripts that were kindly provided by Irene Gialdini
 *
 * Description:
 *     This pipeline is used for pre-processing of DualCam images before DCTracker
*/ 

input = getDir("Select a directory");

list = getFileList(input);
for (i = 0; i < list.length; i++){
    if (endsWith(list[i], ".ome.tiff")) {
        analyse(input + File.separator +  list[i]);
    }
}

function analyse(imageFile) {
    // Create the output directory based on the input file basename 
    basename = File.getName(imageFile);
    nameWithoutExtention = substring(basename, 0, indexOf(basename, "."));
    inputDir = File.getDirectory(imageFile);
    outputDir = inputDir + nameWithoutExtention;
    File.makeDirectory(outputDir);

    // Import the image and split the channels
    // Channels are named basename - C=N where N is the channel number
    run("Bio-Formats Importer", "open=" + imageFile + " " + 
    "autoscale color_mode=Default view=Hyperstack stack_order=XYCZT " + 
    "split_channels");

    // Run bleach correction on both channels
    // Intermediate images are closed
    selectWindow(basename + " - C=0");
    run("Bleach Correction", "correction=[Exponential Fit]");
    selectWindow("y = a*exp(-bx) + c");
    close();
    selectWindow(basename + " - C=0");
    close();

    selectWindow(basename + " - C=1");
    run("Bleach Correction", "correction=[Exponential Fit]");
    selectWindow("y = a*exp(-bx) + c");
    close();
    selectWindow(basename + " - C=1");
    close();

    // Close the log window
    selectWindow("Log");
    run("Close");

    // Let the user draw the nucleus
    // Images are tiled for a faster display
    run("Tile");
    run("Main Window [return]");
    waitForUser("Draw the nucleus\nClick ok to continue");

    // Check that at least one ROI was drawn. Otherwise ask the user again to 
    // draw the 
    nRoi = roiManager("count");
    while (nRoi < 1) {
        waitForUser("Did you forget to draw/save a nucleus ? You have another chance !\nClick ok to continue");
        nRoi = roiManager("count");
    }

    // Deselect any ROI 
    roiManager("show all");
    roiManager("show none");

    selectWindow("DUP_" + basename + " - C=1");
    run("Subtract Background...", "rolling=10 stack");
    run("Duplicate...", "duplicate");
    run("Enhance Contrast", "auto");
    run("Subtract...");
    run("Mexican Hat Filter", "radius=4 stack");
    run("8-bit");
    setThreshold(1, 255);
    setOption("BlackBackground", false);
    run("Convert to Mask", "method=Otsu background=Light black");
    saveAs("Tiff", outputDir + File.separator + "mask.tif");
    close();

    // Run TrackMate for every ROI for current image 
    n = roiManager('count');
    for (i = 0; i < n; i++) {
        roiManager('select', i);
        roiManager("save selected", outputDir + File.separator + i + ".roi");
        run('TrackMate', "use_gui=True radius=0.265 threshold=200 " +
        "median=True max_frame_gap=3 max_distance=0.2 " +
        "max_gap_distance=0.2");
        waitForUser("Display Next TrackMate");
    }

    // Switch to other image and run TrackMate for every ROI again
    selectWindow("DUP_" + basename + " - C=0");
    n = roiManager('count');
    for (i = 0; i < n; i++) {
        roiManager('select', i);
        run('TrackMate', "use_gui=True radius=0.265 threshold=70 " +
        "median=True max_frame_gap=0 max_distance=0.8 " +
        "max_gap_distance=0");
        waitForUser("Display Next TrackMate");
    }

    // Cleanup the environment
    while (nImages>0) { 
        selectImage(nImages); 
        close(); 
    } 
    selectWindow("ROI Manager");
    run("Close");
}