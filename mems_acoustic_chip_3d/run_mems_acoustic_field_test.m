function results = run_mems_acoustic_field_test()
%RUN_MEMS_ACOUSTIC_FIELD_TEST Build, solve, compare, and export test results.

model = build_mems_acoustic_chip_3d();
reference = mems_acoustic_reference_frequencies(12);

raw_frequency = real(mphglobal(model, 'freq'));
computed = sort(raw_frequency(raw_frequency > 1));
count = min(height(reference), numel(computed));

results = reference(1:count, :);
results.computed_hz = computed(1:count);
results.relative_error_percent = ...
    100*abs(results.computed_hz-results.frequency_hz)./results.frequency_hz;

writetable(results, 'mems_acoustic_mode_validation.csv');
disp(results);

figure('Color', 'white');
plot(results.frequency_hz/1e3, results.computed_hz/1e3, 'o', 'LineWidth', 1.5);
hold on;
limits = [0, 1.05*max(results.frequency_hz/1e3)];
plot(limits, limits, '--', 'LineWidth', 1);
xlim(limits);
ylim(limits);
axis square;
grid on;
xlabel('Analytical frequency (kHz)');
ylabel('COMSOL frequency (kHz)');
title('3D MEMS Acoustic Cavity Validation');
exportgraphics(gcf, 'mems_acoustic_mode_validation.png', 'Resolution', 180);

figure('Color', 'white');
mphplot(model, 'pg_pressure');
exportgraphics(gcf, 'mems_acoustic_pressure_mode.png', 'Resolution', 180);

Lx = 2e-3;
x = linspace(-Lx/2, Lx/2, 201);
coordinates = [x; zeros(size(x)); (300e-6 + 0.25e-3)*ones(size(x))];
[~, first_mode_solnum] = min(abs(raw_frequency - reference.frequency_hz(1)));
p_line = real(mphinterp(model, 'acoustic.p', 'coord', coordinates, ...
    'dataset', 'dset1', 'solnum', first_mode_solnum));
p_line = p_line(:);
p_normalized = p_line/max(abs(p_line));
p_analytical = cos(pi*(x(:) + Lx/2)/Lx);
shape_correlation = abs(dot(p_normalized, p_analytical) / ...
    (norm(p_normalized)*norm(p_analytical)));

centerline = table(x(:), p_line, p_normalized, p_analytical, ...
    'VariableNames', {'x_m', 'pressure_pa', 'normalized_pressure', ...
    'analytical_mode_100'});
writetable(centerline, 'mems_acoustic_centerline_pressure.csv');

figure('Color', 'white');
plot(x*1e3, p_normalized, 'LineWidth', 1.5);
hold on;
plot(x*1e3, p_analytical, '--', 'LineWidth', 1.2);
grid on;
xlabel('Centerline x (mm)');
ylabel('Normalized pressure');
title(sprintf('First Acoustic Mode Shape, |correlation| = %.6f', shape_correlation));
legend('COMSOL', 'Analytical (1,0,0)', 'Location', 'best');
exportgraphics(gcf, 'mems_acoustic_centerline_pressure.png', 'Resolution', 180);

fprintf('Maximum compared-mode relative error: %.3f %%\n', ...
    max(results.relative_error_percent));
fprintf('First-mode centerline shape correlation: %.6f\n', shape_correlation);
end
