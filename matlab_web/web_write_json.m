function web_write_json(filename, data)
% WEB_WRITE_JSON UTF-8 data export. No controller code is executed by the website.
folder = fileparts(filename);
if ~isempty(folder) && ~isfolder(folder)
    mkdir(folder);
end
fid = fopen(filename, 'w', 'n', 'UTF-8');
assert(fid >= 0, 'Cannot open JSON destination.');
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
fprintf(fid, '%s', jsonencode(data));
fprintf('Web export saved: %s\n', filename);
end
