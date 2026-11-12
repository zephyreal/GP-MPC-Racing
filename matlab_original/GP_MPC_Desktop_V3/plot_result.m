function plot_result(out)
n=out.steps;
figure('Name',['GP-MPC V2: ',out.mode],'Color','w');
subplot(2,2,1); hold on; axis equal; grid on;
plot(out.track_l(1,:),out.track_l(2,:),'k-');
plot(out.track_r(1,:),out.track_r(2,:),'k-');
plot(out.track_c(1,:),out.track_c(2,:),'k:');
plot(out.x(1,1:n+1),out.x(2,1:n+1),'b-','LineWidth',1.5);
xlabel('x [m]'); ylabel('y [m]'); title('Trajectory (original full-size model)');
subplot(2,2,2); plot(out.t(1:n),out.solve_seconds(1:n)); hold on;
yline(out.cfg.dt,'r--'); grid on; title('Solver time'); xlabel('Simulation time [s]'); ylabel('Wall time [s]');
subplot(2,2,3); plot(out.t(1:n),out.contour_error(1:n)); grid on;
title('Lateral error relative to progress reference'); xlabel('Time [s]'); ylabel('Error [m]');
subplot(2,2,4); plot(out.t(1:n),out.u(1:2,1:n)'); grid on;
legend('Steering [rad]','Torque gain'); title('Physical controls'); xlabel('Time [s]');
end
