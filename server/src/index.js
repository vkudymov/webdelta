import express from 'express';
import cors from 'cors';
import { initDb } from './db.js';
import pagesRouter from './routes/pages.js';

const app = express();
const PORT = process.env.PORT || 3001;

app.use(cors());
app.use(express.json({ limit: '50mb' }));

initDb();

app.use('/api/pages', pagesRouter);

app.get('/api/health', (req, res) => {
  res.json({ status: 'ok', timestamp: new Date().toISOString() });
});

app.listen(PORT, () => {
  console.log(`WebDelta server running on http://localhost:${PORT}`);
});
