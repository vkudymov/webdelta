export function compareTexts(oldText, newText) {
  const oldLines = oldText.split('\n');
  const newLines = newText.split('\n');
  const maxLines = Math.max(oldLines.length, newLines.length);
  
  const changes = [];

  for (let i = 0; i < maxLines; i++) {
    const lineNum = i + 1;
    const oldLine = oldLines[i] ?? '';
    const newLine = newLines[i] ?? '';

    if (oldLine !== newLine) {
      if (i >= oldLines.length) {
        changes.push({
          type: 'added',
          lineNumber: lineNum,
          original: null,
          current: newLine,
        });
      } else if (i >= newLines.length) {
        changes.push({
          type: 'removed',
          lineNumber: lineNum,
          original: oldLine,
          current: null,
        });
      } else {
        changes.push({
          type: 'modified',
          lineNumber: lineNum,
          original: oldLine,
          current: newLine,
        });
      }
    }
  }

  const hasChanges = changes.length > 0;
  
  const stats = {
    additions: changes.filter(c => c.type === 'added').length,
    deletions: changes.filter(c => c.type === 'removed').length,
    modifications: changes.filter(c => c.type === 'modified').length,
    totalLines: maxLines,
    changedLines: changes.length,
  };

  return {
    hasChanges,
    changes,
    stats,
  };
}

export function compareAttachmentText(oldContent, newContent) {
  if (!oldContent || !newContent) {
    return { hasChanges: true, changes: [], stats: { error: 'missing content' } };
  }

  let oldText, newText;
  try {
    oldText = typeof oldContent === 'string' ? oldContent : oldContent.toString('utf8');
    newText = typeof newContent === 'string' ? newContent : newContent.toString('utf8');
  } catch {
    return { hasChanges: false, changes: [], stats: { binary: true } };
  }

  return compareTexts(oldText, newText);
}

export function compareAttachments(savedAttachments, currentAttachments) {
  const savedMap = new Map(savedAttachments.map(a => [a.url, a]));
  const currentMap = new Map(currentAttachments.map(a => [a.url, a]));

  const added = [];
  const removed = [];
  const modified = [];
  const unchanged = [];

  for (const [url, current] of currentMap) {
    const saved = savedMap.get(url);
    
    if (!saved) {
      added.push({
        url,
        filename: current.filename,
        contentType: current.contentType,
        size: current.size,
      });
    } else if (saved.hash !== current.hash) {
      const isTextType = isTextContentType(current.contentType);
      let textDiff = null;
      
      if (isTextType) {
        textDiff = compareAttachmentText(saved.content, current.content);
      }

      modified.push({
        url,
        filename: current.filename,
        contentType: current.contentType,
        oldSize: saved.size,
        newSize: current.size,
        oldHash: saved.hash,
        newHash: current.hash,
        textDiff,
      });
    } else {
      unchanged.push({
        url,
        filename: current.filename,
        contentType: current.contentType,
        size: current.size,
      });
    }
  }

  for (const [url, saved] of savedMap) {
    if (!currentMap.has(url)) {
      removed.push({
        url,
        filename: saved.filename,
        contentType: saved.content_type || saved.contentType,
        size: saved.size,
      });
    }
  }

  return { added, removed, modified, unchanged };
}

function isTextContentType(contentType) {
  if (!contentType) return false;
  const textTypes = [
    'text/', 'application/json', 'application/xml', 
    'application/javascript', 'application/csv'
  ];
  return textTypes.some(t => contentType.includes(t));
}
