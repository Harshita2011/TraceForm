// Reserve multipart overhead below hosted function payload limits.
const configured=Number(process.env.NEXT_PUBLIC_UPLOAD_MAX_BYTES||4000000);
export const UPLOAD_MAX_BYTES=Number.isFinite(configured)&&configured>0?configured:4000000;
export const UPLOAD_MAX_MB=(UPLOAD_MAX_BYTES/1000000).toLocaleString(undefined,{maximumFractionDigits:1});
