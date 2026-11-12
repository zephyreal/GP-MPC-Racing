function value = web_sha256(filename)
% WEB_SHA256 Hash original file bytes, not decoded/re-encoded text.
fid = fopen(filename, 'rb');
assert(fid >= 0, 'Cannot read original source file.');
cleanup = onCleanup(@() fclose(fid)); %#ok<NASGU>
bytes = fread(fid, Inf, '*uint8');
if ~usejava('jvm')
    value = '';
    return
end
engine = javaMethod('getInstance', 'java.security.MessageDigest', 'SHA-256');
engine.update(bytes);
raw = typecast(engine.digest(), 'uint8');
value = lower(reshape(dec2hex(raw, 2)', 1, []));
end
