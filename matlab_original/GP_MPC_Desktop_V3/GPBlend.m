classdef GPBlend < handle
    % A mutable, conservatively blended residual model.
    properties
        model = []
        gain = 0.3
    end
    methods
        function [mu,V]=predict(obj,z)
            if isempty(obj.model)
                mu=zeros(3,size(z,2));
                if nargout>1,V=zeros(3,3,size(z,2));end
            elseif nargout<2
                mu=obj.gain*obj.model.eval(z);
            else
                [mu,V]=obj.model.eval(z);
                mu=obj.gain*mu; V=obj.gain^2*V;
            end
        end
    end
end
