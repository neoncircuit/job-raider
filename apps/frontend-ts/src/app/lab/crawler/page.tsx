import { CrawlerReplay } from "@/components/crawler-replay";
import { PageContainer } from "@/components/layout/PageContainer";
import { PageHeader } from "@/components/layout/PageHeader";
import { SAMPLE_TRACE } from "@/lib/crawler-trace";

/**
 * Prototype page that replays how a listing page is read.
 *
 * Uses a hand-written sample trace; it is not connected to the scrapers.
 *
 * @returns The crawler replay lab page.
 */
export default function CrawlerLabPage() {
  return (
    <PageContainer variant="wide">
      <PageHeader
        title="Crawler replay (prototype)"
        subtitle="Watch each extraction decision on a listing page: kept, discarded, or flagged. Sample trace only; not live scraper output."
      />
      <CrawlerReplay trace={SAMPLE_TRACE} />
    </PageContainer>
  );
}
