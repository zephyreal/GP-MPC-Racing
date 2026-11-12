% Unzip the complete project. Restart MATLAB if V2 classes were loaded.
% Set Current Folder here, then run this script.
out = run_learning(struct('laps',5,'learn',true,'live',true));
% Baseline without GP updates, same control objective:
% baseline = run_learning(struct('laps',5,'learn',false,'live',true));
% Runtime includes graphics; use live=false for compute-only comparisons.
