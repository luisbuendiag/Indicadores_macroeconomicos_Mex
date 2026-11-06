// Shared validation for file selection and drag-and-drop. PDF contents are checked next.
export function pdfFromFiles(files) {
  if (!files.length) return null;
  if (files.length !== 1) throw new Error('Carga un solo boletín PDF a la vez.');
  const file = files[0];
  if (!/\.pdf$/i.test(file.name || '') && file.type !== 'application/pdf') {
    throw new Error('Selecciona o arrastra un archivo PDF.');
  }
  return file;
}
