function table_out = acoustic_rectangular_cavity_reference_frequencies()
%ACOUSTIC_RECTANGULAR_CAVITY_REFERENCE_FREQUENCIES Analytical test values.

c_air = 343;
Lx = 4;
Ly = 3;

mode_m = [1; 0; 1; 2];
mode_n = [0; 1; 1; 0];
frequency_hz = c_air/2 .* sqrt((mode_m/Lx).^2 + (mode_n/Ly).^2);

table_out = table(mode_m, mode_n, frequency_hz);
end
