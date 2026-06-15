function table_out = mems_acoustic_reference_frequencies(count)
%MEMS_ACOUSTIC_REFERENCE_FREQUENCIES Sorted analytical rigid-cavity modes.

if nargin < 1
    count = 12;
end

c_air = 343;
Lx = 2e-3;
Ly = 1.5e-3;
Hcav = 0.5e-3;

[m, n, q] = ndgrid(0:4, 0:4, 0:2);
modes = [m(:), n(:), q(:)];
modes(~any(modes, 2), :) = [];
frequency_hz = c_air/2 .* sqrt( ...
    (modes(:,1)./Lx).^2 + (modes(:,2)./Ly).^2 + (modes(:,3)./Hcav).^2);

[frequency_hz, order] = sort(frequency_hz);
modes = modes(order, :);
count = min(count, size(modes, 1));
modes = modes(1:count, :);
frequency_hz = frequency_hz(1:count);

table_out = table(modes(:,1), modes(:,2), modes(:,3), frequency_hz, ...
    'VariableNames', {'m', 'n', 'q', 'frequency_hz'});
end
