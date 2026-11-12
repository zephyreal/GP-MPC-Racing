function ui=live_dashboard(action,varargin)
% Reuse graphics handles: no re-creation of axes at each sample.
ui=[];
switch action
case 'init'
    track=varargin{1};
    ui.fig=figure('Name','GP-MPC V3 | Live laps','Color','w','Position',[80 80 1150 700]);
    setappdata(ui.fig,'stopRequested',false);
    ui.ax=subplot(2,2,[1 3]);hold on;axis equal;grid on;
    plot(track.track_l(1,:),track.track_l(2,:),'k-');plot(track.track_r(1,:),track.track_r(2,:),'k-');
    plot(track.track_c(1,:),track.track_c(2,:),'Color',[.7 .7 .7]);
    ui.path=plot(NaN,NaN,'b-');ui.pred=plot(NaN,NaN,'--','Color',[.9 .5 .1]);
    ui.car=patch(NaN,NaN,[.9 .15 .15],'EdgeColor','none');
    xlabel('x [m]');ylabel('y [m]');title('Original full-size vehicle model');
    subplot(2,2,2);ui.speed=plot(NaN,NaN,'b-');grid on;xlabel('Simulation time [s]');ylabel('Speed [m/s]');
    subplot(2,2,4);ui.laps=plot(NaN,NaN,'o-','LineWidth',1.5);grid on;xlabel('Completed lap');ylabel('Lap time [simulation s]');
    ui.status=annotation('textbox',[.05 .92 .9 .07],'String','Initializing...', ...
        'EdgeColor','none','Interpreter','none','FontSize',11);
    uicontrol(ui.fig,'Style','pushbutton','String','Stop and save','Units','normalized', ...
        'Position',[.82 .01 .15 .04],'Callback',@(src,event) setappdata(ancestor(src,'figure'),'stopRequested',true));
    drawnow;
case 'update'
    ui=varargin{1};out=varargin{2};k=varargin{3};prediction=varargin{4};status=varargin{5};
    if ~isgraphics(ui.fig),return;end
    x=out.x(:,k+1);R=[cos(x(3)),-sin(x(3));sin(x(3)),cos(x(3))];
    vertices=R*[2,-1,-1;0,.8,-.8]+x(1:2);
    set(ui.car,'XData',vertices(1,:),'YData',vertices(2,:));
    start=max(1,k-3000);set(ui.path,'XData',out.x(1,start:k+1),'YData',out.x(2,start:k+1));
    set(ui.pred,'XData',prediction(1,:),'YData',prediction(2,:));
    set(ui.speed,'XData',out.t(1:k+1),'YData',hypot(out.x(4,1:k+1),out.x(5,1:k+1)));
    if ~isempty(out.laps),set(ui.laps,'XData',[out.laps.index],'YData',[out.laps.seconds]);end
    set(ui.status,'String',status);drawnow;
case 'message'
    ui=varargin{1};if isgraphics(ui.fig),set(ui.status,'String',varargin{2});drawnow;end
end
end
