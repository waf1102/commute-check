/// <reference types="vitest" />
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';


export default defineConfig({
	plugins: [
		sveltekit(),
	],
	resolve: {
		conditions: process.env.VITEST ? ['browser'] : undefined
	},
	test: {
		include: ['src/**/*.{test,spec}.{js,ts}'],
		environment: 'jsdom',
		setupFiles: ['./src/setupTest.ts'],
		globals: true
	}
});