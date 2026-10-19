import { Router } from 'express';
import { getDb } from '../db.js';
import { fetchPageContent, fetchAttachments, extractAttachmentLinks } from '../services/fetcher.js';
import { compareTexts, compareAttachments } from '../services/differ.js';

const router = Router();

router.get('/check', async (req, res) => {
  try {
    const { url } = req.query;
    if (!url) {
      return res.status(400).json({ error: 'URL is required' });
    }

    const db = getDb();
    const page = db.prepare('SELECT id, url, title, created_at, updated_at FROM pages WHERE url = ?').get(url);
    
    if (page) {
      const attachmentCount = db.prepare('SELECT COUNT(*) as count FROM attachments WHERE page_id = ?').get(page.id);
      res.json({ 
        exists: true, 
        page: { ...page, attachmentCount: attachmentCount.count }
      });
    } else {
      res.json({ exists: false });
    }
  } catch (error) {
    console.error('Check error:', error);
    res.status(500).json({ error: error.message });
  }
});

router.post('/download', async (req, res) => {
  try {
    const { url, overwrite = false } = req.body;
    
    if (!url) {
      return res.status(400).json({ error: 'URL is required' });
    }

    try {
      new URL(url);
    } catch {
      return res.status(400).json({ error: 'Invalid URL format' });
    }

    const db = getDb();
    const existingPage = db.prepare('SELECT id FROM pages WHERE url = ?').get(url);

    if (existingPage && !overwrite) {
      return res.status(409).json({ 
        error: 'Page already exists',
        requiresConfirmation: true 
      });
    }

    console.log(`Fetching page: ${url}`);
    const { content, title } = await fetchPageContent(url);
    
    console.log(`Extracting attachments from: ${url}`);
    const attachmentLinks = extractAttachmentLinks(content, url);
    console.log(`Found ${attachmentLinks.length} attachments`);

    const attachments = await fetchAttachments(attachmentLinks);
    console.log(`Successfully fetched ${attachments.length} attachments`);

    if (existingPage) {
      db.prepare('DELETE FROM attachments WHERE page_id = ?').run(existingPage.id);
      db.prepare(`
        UPDATE pages SET content = ?, title = ?, updated_at = datetime('now') WHERE id = ?
      `).run(content, title, existingPage.id);

      const insertAttachment = db.prepare(`
        INSERT INTO attachments (page_id, url, filename, content_type, content, size, hash)
        VALUES (?, ?, ?, ?, ?, ?, ?)
      `);

      for (const att of attachments) {
        insertAttachment.run(
          existingPage.id, att.url, att.filename, att.contentType, 
          att.content, att.size, att.hash
        );
      }

      res.json({ 
        success: true, 
        message: 'Page updated',
        pageId: existingPage.id,
        attachmentCount: attachments.length
      });
    } else {
      const result = db.prepare(`
        INSERT INTO pages (url, content, title) VALUES (?, ?, ?)
      `).run(url, content, title);

      const pageId = result.lastInsertRowid;

      const insertAttachment = db.prepare(`
        INSERT INTO attachments (page_id, url, filename, content_type, content, size, hash)
        VALUES (?, ?, ?, ?, ?, ?, ?)
      `);

      for (const att of attachments) {
        insertAttachment.run(
          pageId, att.url, att.filename, att.contentType,
          att.content, att.size, att.hash
        );
      }

      res.json({ 
        success: true, 
        message: 'Page saved',
        pageId,
        attachmentCount: attachments.length
      });
    }
  } catch (error) {
    console.error('Download error:', error);
    res.status(500).json({ error: error.message });
  }
});

router.post('/compare', async (req, res) => {
  try {
    const { url } = req.body;
    
    if (!url) {
      return res.status(400).json({ error: 'URL is required' });
    }

    const db = getDb();
    const page = db.prepare('SELECT * FROM pages WHERE url = ?').get(url);

    if (!page) {
      return res.status(404).json({ error: 'No saved version found for this URL' });
    }

    const savedAttachments = db.prepare('SELECT * FROM attachments WHERE page_id = ?').all(page.id);

    console.log(`Fetching current version: ${url}`);
    const { content: currentContent, title: currentTitle } = await fetchPageContent(url);
    
    const currentAttachmentLinks = extractAttachmentLinks(currentContent, url);
    const currentAttachments = await fetchAttachments(currentAttachmentLinks);

    const textDiff = compareTexts(page.content, currentContent);
    const attachmentDiffs = compareAttachments(savedAttachments, currentAttachments);

    res.json({
      success: true,
      comparison: {
        url,
        savedTitle: page.title,
        currentTitle,
        savedAt: page.updated_at,
        textDiff,
        attachmentDiffs,
        summary: {
          textChanged: textDiff.hasChanges,
          attachmentsAdded: attachmentDiffs.added.length,
          attachmentsRemoved: attachmentDiffs.removed.length,
          attachmentsModified: attachmentDiffs.modified.length,
          attachmentsUnchanged: attachmentDiffs.unchanged.length
        }
      }
    });
  } catch (error) {
    console.error('Compare error:', error);
    res.status(500).json({ error: error.message });
  }
});

router.get('/list', (req, res) => {
  try {
    const db = getDb();
    const pages = db.prepare(`
      SELECT p.id, p.url, p.title, p.created_at, p.updated_at,
             (SELECT COUNT(*) FROM attachments WHERE page_id = p.id) as attachment_count
      FROM pages p
      ORDER BY p.updated_at DESC
    `).all();

    res.json({ pages });
  } catch (error) {
    console.error('List error:', error);
    res.status(500).json({ error: error.message });
  }
});

router.delete('/:id', (req, res) => {
  try {
    const { id } = req.params;
    const db = getDb();
    
    db.prepare('DELETE FROM attachments WHERE page_id = ?').run(id);
    const result = db.prepare('DELETE FROM pages WHERE id = ?').run(id);

    if (result.changes > 0) {
      res.json({ success: true, message: 'Page deleted' });
    } else {
      res.status(404).json({ error: 'Page not found' });
    }
  } catch (error) {
    console.error('Delete error:', error);
    res.status(500).json({ error: error.message });
  }
});

export default router;
