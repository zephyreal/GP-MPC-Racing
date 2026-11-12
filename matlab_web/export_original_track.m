function data = export_original_track(filename)
% EXPORT_ORIGINAL_TRACK Use original MATLAB class to export centre/left/right coordinates.
% addpath('matlab_web'); export_original_track('results/track02-native.json');
if nargin < 1
    root = fileparts(fileparts(mfilename('fullpath')));
    filename = fullfile(root, 'results', 'track02-native.json');
end
data = web_track02();
web_write_json(filename, data);
end
