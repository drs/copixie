// placeholder for file/directory
configPath = "";
metadataPath = "";
inputPath = "";
outputPath = "";

// keep the dialog active until valid values are provided
while (true) {
  // create the dialog window
  Dialog.create("Run CoPixie");
  Dialog.addFile("Configuration:", configPath);
  Dialog.addFile("Metadata:", metadataPath);
  Dialog.addDirectory("Input:", inputPath);
  Dialog.addDirectory("Output:", outputPath);
  Dialog.show();
    
  configPath = Dialog.getString();
  metadataPath = Dialog.getString();
  inputPath = Dialog.getString();
  outputPath = Dialog.getString();
    
  // validate the user inputs
  if (metadataPath != "" && inputPath != "") {
    showMessage("Error", "Please select either a Metadata file or an Input directory, but not both.");
  }
  else if (configPath == "" || outputPath == "" || (metadataPath == "" && inputPath == "")) {
    showMessage("Error", "The configuration file, output path and a metatada or input directory are required to run CoPixie.");validInput = false;
  }
  else {
    break;
  }
}

// run copixie
configArg = "-с " + configPath;
outputArg = "-о " + outputPath;
metadataArg = "-m " + metadataPath;
command = "copixie" + " " + configArg + " " + outputArg + " " + metadataArg;
output = exec(command);
