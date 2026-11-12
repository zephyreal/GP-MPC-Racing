% Unzip the ENTIRE folder and set MATLAB Current Folder here.
% If the original project was used in the same MATLAB session, restart MATLAB
% first to prevent old class definitions being reused.
out = run_demo('fast');
% For a longer simulation: out = run_demo('fast',struct('tf',180));
% Fewer control variables: out = run_demo('compact');
% Controlled timing comparison: results = benchmark_v2;
