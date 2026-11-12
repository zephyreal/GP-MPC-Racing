function cost = race_cost(mu_x, var_x, u, track)

    % Track oriented penalization
    q_l   = 50;     % penalization of lag error
    q_c   = 20;     % penalization of contouring error
    q_o   = 5;      % penalization for orientation error
    q_d   = -3;     % reward high track centerline velocites
    q_r   = 100;    % penalization when vehicle is outside track
    
    % state and input penalization
    q_v      = -0;  % reward high absolute velocities
    q_st     =  0;  % penalization of steering
    q_br     =  0;  % penalization of breaking
    q_psidot =  8;  % penalize high yaw rates
    q_acc    = -0;  % reward for accelerating

    % label inputs and outputs
    I_x        = mu_x(1);  % x position in global coordinates
    I_y        = mu_x(2);  % y position in global coordinates
    psi        = mu_x(3);  % yaw
    V_vx       = mu_x(4);  % x velocity in vehicle coordinates
    V_vy       = mu_x(5);  % x velocity in vehicle coordinates
    psidot     = mu_x(6);
    track_dist = mu_x(7);  % track centerline distance
    delta      = u(1);     % steering angle rad2deg(delta)
    T          = u(2);     % torque gain (1=max.acc, -1=max.braking)
    track_vel  = u(3);     % track centerline velocity
    

    % ---------------------------------------------------------------------
    % cost of contour, lag and orientation error
    % ---------------------------------------------------------------------

    % get lag, contour, offroad and orientation error of the vehicle w.r.t.
    % a point in the trajectory that is 'track_dist' far away from the 
    % origin along the track centerline (traveled distance)
    [lag_error, countour_error, offroad_error, orientation_error] = ...
        track.getVehicleDeviation([I_x;I_y], psi, track_dist);
    
    cost_contour     = q_c * countour_error^2;
    cost_lag         = q_l * lag_error^2;
    cost_orientation = q_o * orientation_error^2;
    
    % ---------------------------------------------------------------------
    % cost for being outside track
    % ---------------------------------------------------------------------
    % % apply smooth barrier function (we want: offroad_error < 0). 
    % alpha = 40; % smoothing factor... the smaller the smoother
    % offroad_error = (1+exp(-alpha*(offroad_error+0.05))).^-1;
    gamma = 1000;
    lambda = -0.1;
    offroad_error = 5*(sqrt((4+gamma*(lambda-offroad_error).^2)/gamma) - (lambda-offroad_error));
    cost_outside = q_r * offroad_error^2;
    
    % ---------------------------------------------------------------------
    % reward high velocities
    % ---------------------------------------------------------------------
    cost_vel = q_v * norm([V_vx; V_vy]);
    
    % ---------------------------------------------------------------------
    % penalize high yaw rates
    % ---------------------------------------------------------------------
    cost_psidot = q_psidot * psidot^2;
    
    % ---------------------------------------------------------------------
    % reward high track velocities
    % ---------------------------------------------------------------------
    cost_dist = q_d * track_vel;
    
    % ---------------------------------------------------------------------
    % penalize acceleration, braking and steering
    % ---------------------------------------------------------------------
    cost_inputs = (T>0)*q_acc*T^2 + (T<0)*q_br*T^2 + q_st*(delta)^2 ;
    
    % ---------------------------------------------------------------------
    % Calculate final cost
    % ---------------------------------------------------------------------
    cost = cost_contour + ...
           cost_lag + ...
           cost_orientation + ...
           cost_dist + ...
           cost_outside + ...
           cost_inputs + ...
           cost_vel + ...
           cost_psidot;
end