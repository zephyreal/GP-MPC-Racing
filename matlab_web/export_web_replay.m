function data = export_web_replay(teacher, student, filename)
% EXPORT_WEB_REPLAY Display ORIGINAL run_learning outputs side by side in the browser.
% Inputs are output structs, or trusted MAT files containing variable 'out'.
% This adapter never changes original dynamics, cost, NMPC, GP, or map classes.
% Imported recordings are for visualisation; they are NOT official online grades.
if nargin < 3
    root = fileparts(fileparts(mfilename('fullpath')));
    filename = fullfile(root, 'results', 'matlab-original-dual-replay.json');
end
teacher = readout(teacher);
student = readout(student);
track = web_track02();
checkmap(teacher, track);
checkmap(student, track);
target = 1;
if isfield(teacher.cfg, 'laps')
    target = teacher.cfg.laps;
end
if isfield(student.cfg, 'laps')
    assert(student.cfg.laps == target, 'Teacher/student target laps differ.');
end
data = struct('schema', 'matlab-original-dual-replay-v1', ...
    'recording_only', true, 'track', track, ...
    'config', struct('engine', 'matlab-original-v3-replay', 'laps', target, ...
    'track', 'track02-original-v1', 'recording_only', true), ...
    'teacher', convert(teacher, track.length, target), ...
    'student', convert(student, track.length, target));
data.provenance = struct('kind', 'local-matlab-export', 'matlab_release', version('-release'), ...
    'source_sha256', track.source.sha256, 'note', ...
    'Original outputs preserved; imported recording does not enter an official leaderboard.');
web_write_json(filename, data);
end

function out = readout(value)
if ischar(value) || isstring(value)
    saved = load(value, 'out');
    assert(isfield(saved, 'out'), 'MAT file must contain out.');
    out = saved.out;
else
    out = value;
end
required = {'x', 'u', 't', 'steps', 'cfg', 'track_c', 'track_l', 'track_r'};
for i = 1:numel(required)
    assert(isfield(out, required{i}), 'Missing original output field: %s', required{i});
end
assert(size(out.x, 1) == 7, 'Expected original 7-state vehicle output.');
assert(size(out.u, 1) == 3, 'Expected original 3-input NMPC output.');
assert(out.steps >= 1 && out.steps == floor(out.steps), 'Invalid step count.');
assert(numel(out.t) >= out.steps + 1 && size(out.x, 2) >= out.steps + 1, 'Incomplete state/time arrays.');
assert(size(out.u, 2) >= out.steps, 'Incomplete control array.');
end

function checkmap(out, track)
assert(isequal(size(out.track_c), size(track.points')), 'Original map dimensions differ.');
assert(max(abs(out.track_c(:) - reshape(track.points', [], 1))) < 1e-7, 'Original centreline differs.');
assert(max(abs(out.track_l(:) - reshape(track.left', [], 1))) < 1e-7, 'Original left boundary differs.');
assert(max(abs(out.track_r(:) - reshape(track.right', [], 1))) < 1e-7, 'Original right boundary differs.');
end

function result = convert(out, lengthTrack, target)
n = out.steps;
assert(all(all(isfinite(out.x(:, 1:n+1)))), 'Original output contains invalid states.');
assert(all(all(isfinite(out.u(:, 1:n)))), 'Original output contains invalid controls.');
assert(all(diff(out.t(1:n+1)) > 0), 'Time must increase.');
if isfield(out, 'progress') && numel(out.progress) >= n + 1
    progress = out.progress(1:n+1);
else
    ds = mod(diff(out.x(7, 1:n+1)) + lengthTrack/2, lengthTrack) - lengthTrack/2;
    progress = [0, cumsum(ds)];
end
laps = struct([]);
if isfield(out, 'laps')
    laps = out.laps;
end
lapTimes = [];
if ~isempty(laps)
    lapTimes = [laps.seconds];
end
ends = cumsum(lapTimes);
empty = struct('t', 0, 'state', zeros(1, 6), 'original_state', zeros(1, 7), ...
    'action', [0, 0], 'original_control', [0, 0, 0], 'progress', 0, ...
    'solve_ms', 0, 'telemetry', struct());
frames = repmat(empty, 1, n + 1);
for i = 1:n+1
    frames(i).t = out.t(i);
    frames(i).state = out.x(1:6, i)';
    frames(i).original_state = out.x(:, i)';
    frames(i).progress = progress(i);
    telemetry = struct('gp_active', false, 'gp_update', 'Original MATLAB lap record');
    idx = find(out.t(i) <= ends + 1e-8, 1, 'first');
    if isempty(idx) && ~isempty(laps)
        idx = numel(laps);
    end
    if ~isempty(idx) && isfield(laps, 'usedGP')
        telemetry.gp_active = logical(laps(idx).usedGP);
    end
    previous = find(out.t(i) >= ends, 1, 'last');
    if ~isempty(previous) && isfield(laps, 'updateReason')
        telemetry.gp_update = laps(previous).updateReason;
    end
    if i > 1
        k = i - 1;
        frames(i).action = out.u(1:2, k)';
        frames(i).original_control = out.u(:, k)';
        if isfield(out, 'solve_seconds') && isfinite(out.solve_seconds(k))
            frames(i).solve_ms = 1000*out.solve_seconds(k);
        end
        if isfield(out, 'exitflag')
            telemetry.solver_ok = out.exitflag(k) > 0;
        end
        if isfield(out, 'train_seconds')
            telemetry.train_ms = 1000*out.train_seconds(k);
        end
    end
    % No prediction path is invented: original run_learning does not save it.
    frames(i).telemetry = telemetry;
end
status = 'timeout';
reason = 'Original output stopped before target laps';
seconds = out.t(n+1);
if numel(lapTimes) >= target
    status = 'completed';
    reason = '';
    seconds = sum(lapTimes(1:target));
elseif isfield(out, 'stopped_reason') && ~isempty(out.stopped_reason)
    status = 'failed';
    reason = out.stopped_reason;
end
lateralRMSE = 0;
if isfield(out, 'contour_error')
    finiteError = out.contour_error(1:n);
    finiteError = finiteError(isfinite(finiteError));
    if ~isempty(finiteError)
        lateralRMSE = sqrt(mean(finiteError.^2));
    end
end
result = struct('status', status, 'reason', reason, 'completed_laps', numel(lapTimes), ...
    'lap_times', {num2cell(lapTimes)}, 'simulated_seconds', seconds, ...
    'progress', min(1, max(0, progress(end)/(target*lengthTrack))), ...
    'lateral_rmse', lateralRMSE, 'mean_solve_ms', mean([frames(2:end).solve_ms]), ...
    'frames', frames, 'original_cfg', out.cfg, 'original_laps', laps);
end
