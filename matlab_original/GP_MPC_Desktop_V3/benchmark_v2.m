function results=benchmark_v2(tf,repeats)
% Same model, objective, horizon, solver settings and GP-disabled workload.
% 'reference' recreates costly prediction/interpolation paths, NOT the entire
% original program (no online GP updates or graphics in any benchmark mode).
if nargin<1, tf=3; end
if nargin<2, repeats=3; end
assert(repeats>=1 && repeats==floor(repeats));
modes={'reference','fast','compact'};
config=struct('tf',tf,'saveResults',false,'plotResults',false,'progressEvery',0);
fprintf('Warming up MATLAB and solver...\n');
run_demo('fast',struct('tf',0.15,'saveResults',false,'plotResults',false,'progressEvery',0));
results=cell(repeats,3);
for j=1:repeats
    order=circshift(1:3,[0,j-1]);
    for i=order
        results{j,i}=run_demo(modes{i},config);
    end
end
fprintf('\nmode         median solve [s]   lateral RMSE [m]   failed solves\n');
for i=1:3
    times=[]; errors=[]; failures=0;
    for j=1:repeats
        o=results{j,i}; times=[times,o.solve_seconds(1:o.steps)]; %#ok<AGROW>
        errors=[errors,o.contour_error(1:o.steps)]; %#ok<AGROW>
        failures=failures+sum(o.exitflag(1:o.steps)<=0);
    end
    fprintf('%-12s %.6f            %.6f          %d\n',modes{i},median(times),sqrt(mean(errors.^2)),failures);
end
root=fileparts(mfilename('fullpath')); d=fullfile(root,'results');
if ~isfolder(d),mkdir(d);end
save(fullfile(d,'benchmark_latest.mat'),'results');
end
