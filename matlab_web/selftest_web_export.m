function selftest_web_export()
% SELFTEST_WEB_EXPORT Cross-check browser map against ORIGINAL MATLAB geometry.
% Requires MATLAB but no fmincon run. Does not replace or modify original selftest_v3.
root = fileparts(fileparts(mfilename('fullpath')));
map = web_track02();
translated = jsondecode(fileread(fullfile(root, 'gp_mpc_racing', 'data', 'track02-original-v1.json')));
assert(size(map.points, 1) == 391, 'Unexpected Track02 sample count.');
assert(map.width == 6, 'Original width changed.');
assert(max(abs(map.points(:) - translated.points(:))) < 1e-7, 'Centreline translation differs.');
assert(max(abs(map.left(:) - translated.left(:))) < 1e-7, 'Left boundary translation differs.');
assert(max(abs(map.right(:) - translated.right(:))) < 1e-7, 'Right boundary translation differs.');
assert(max(abs(map.heading(:) - translated.heading(:))) < 1e-7, 'Original headings differ.');
fprintf('Native Track02 and web coordinates match; original source files unchanged.\n');
end
