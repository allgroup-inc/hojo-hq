import express from 'express';
import cors from 'cors';
import freeSlotRoutes from './routes/free-slots.routes';

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(express.json());
app.use(cors());

// Routes
app.use('/api', freeSlotRoutes);

// Health check
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'ok', timestamp: new Date().toISOString() });
});

// Error handler
app.use((err: any, req: any, res: any, next: any) => {
  console.error(err);
  res.status(500).json({ error: 'Internal server error' });
});

// Start server only when run directly (not when imported for testing)
if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`✅ PoC Backend running on http://localhost:${PORT}`);
    console.log(`📍 API Endpoint: http://localhost:${PORT}/api/free-slots/:repId/:date`);
  });
}

export default app;
