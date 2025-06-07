import type { NextApiRequest, NextApiResponse } from 'next';
import axios from 'axios';

const WORKER_URL = process.env.WORKER_URL || 'http://localhost:8000';

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') return res.status(405).end();

  try {
    const { data } = await axios.post(`${WORKER_URL}/flashcards`, req.body);
    res.status(200).json(data);
  } catch (error: any) {
    res.status(500).json({ error: error.message });
  }
}
