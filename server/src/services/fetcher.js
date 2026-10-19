import fetch from 'node-fetch';
import * as cheerio from 'cheerio';
import crypto from 'crypto';
import mime from 'mime-types';

const ATTACHMENT_EXTENSIONS = [
  '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
  '.txt', '.rtf', '.odt', '.ods', '.odp',
  '.zip', '.rar', '.7z', '.tar', '.gz',
  '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp',
  '.mp3', '.mp4', '.avi', '.mov', '.wmv', '.flv', '.webm',
  '.csv', '.json', '.xml'
];

const USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36';

export async function fetchPageContent(url) {
  const response = await fetch(url, {
    headers: {
      'User-Agent': USER_AGENT,
      'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
      'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
    },
    timeout: 30000,
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch page: ${response.status} ${response.statusText}`);
  }

  const html = await response.text();
  const $ = cheerio.load(html);

  $('script').remove();
  $('style').remove();
  $('noscript').remove();
  $('iframe').remove();
  $('nav').remove();
  $('footer').remove();
  $('[role="navigation"]').remove();
  $('[role="banner"]').remove();
  $('[role="contentinfo"]').remove();

  const title = $('title').text().trim() || 
                $('h1').first().text().trim() || 
                'Untitled';

  const content = extractTextContent($);

  return { content, title, html };
}

function extractTextContent($) {
  const mainContent = $('main, article, [role="main"], .content, #content, .main, #main');
  
  let textSource;
  if (mainContent.length > 0) {
    textSource = mainContent.first();
  } else {
    textSource = $('body');
  }

  const lines = [];
  
  textSource.find('h1, h2, h3, h4, h5, h6, p, li, td, th, blockquote, pre, dd, dt').each((_, el) => {
    const text = $(el).text().trim();
    if (text) {
      const tagName = el.tagName.toLowerCase();
      if (tagName.startsWith('h')) {
        lines.push(`\n## ${text}\n`);
      } else if (tagName === 'li') {
        lines.push(`• ${text}`);
      } else {
        lines.push(text);
      }
    }
  });

  if (lines.length === 0) {
    const bodyText = textSource.text()
      .replace(/\s+/g, ' ')
      .trim()
      .split(/\.\s+/)
      .filter(s => s.trim().length > 0)
      .join('.\n');
    return bodyText;
  }

  return lines.join('\n').replace(/\n{3,}/g, '\n\n').trim();
}

export function extractAttachmentLinks(htmlContent, baseUrl) {
  const $ = cheerio.load(htmlContent);
  const links = new Set();
  const base = new URL(baseUrl);

  $('a[href]').each((_, el) => {
    const href = $(el).attr('href');
    if (href) {
      try {
        const absoluteUrl = new URL(href, base).href;
        const lowerHref = href.toLowerCase();
        
        if (ATTACHMENT_EXTENSIONS.some(ext => lowerHref.endsWith(ext))) {
          links.add(absoluteUrl);
        }
      } catch {
      }
    }
  });

  $('img[src]').each((_, el) => {
    const src = $(el).attr('src');
    if (src && !src.startsWith('data:')) {
      try {
        const absoluteUrl = new URL(src, base).href;
        links.add(absoluteUrl);
      } catch {
      }
    }
  });

  return Array.from(links);
}

export async function fetchAttachments(urls) {
  const attachments = [];
  
  for (const url of urls) {
    try {
      const response = await fetch(url, {
        headers: { 'User-Agent': USER_AGENT },
        timeout: 60000,
      });

      if (!response.ok) {
        console.warn(`Failed to fetch attachment ${url}: ${response.status}`);
        continue;
      }

      const buffer = await response.arrayBuffer();
      const content = Buffer.from(buffer);
      const hash = crypto.createHash('md5').update(content).digest('hex');
      
      const contentType = response.headers.get('content-type') || 
                          mime.lookup(url) || 
                          'application/octet-stream';

      const urlPath = new URL(url).pathname;
      const filename = urlPath.split('/').pop() || 'unnamed';

      attachments.push({
        url,
        filename,
        contentType,
        content,
        size: content.length,
        hash,
      });
    } catch (error) {
      console.warn(`Error fetching attachment ${url}:`, error.message);
    }
  }

  return attachments;
}
