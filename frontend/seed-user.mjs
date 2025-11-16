import { PrismaClient } from './src/generated/prisma/index.js';

const prisma = new PrismaClient();

async function main() {
  const userId = 'local-user';
  
  // Check if user already exists
  const existingUser = await prisma.user.findUnique({
    where: { id: userId }
  });
  
  if (existingUser) {
    console.log('Mock user already exists:', userId);
    return;
  }
  
  // Create mock user for local development
  const user = await prisma.user.create({
    data: {
      id: userId,
      email: 'local@development.local',
      name: 'Local Developer',
      emailVerified: true,
      default_font_family: 'TikTokSans-Regular',
      default_font_size: 24,
      default_font_color: '#FFFFFF',
      default_clip_min_length: 10,
      default_clip_target_length: 30,
      default_clip_max_length: 45,
    }
  });
  
  console.log('Created mock user:', user.id, user.email);
}

main()
  .catch((e) => {
    console.error('Error seeding database:', e);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });
