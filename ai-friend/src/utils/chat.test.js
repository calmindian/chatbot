import { isImageRequest } from './chat';

test('recognizes chat requests for generated pictures', () => {
  expect(isImageRequest('Change to a gown and send me a pic')).toBe(true);
  expect(isImageRequest('Tell me about a gown')).toBe(false);
});
