"use client";

import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { profileApi } from "@/lib/api/profile";
import { writeProfileLocationCache } from "@/lib/datetime-prefs";

/**
 * Keep a local cache of profile location for datetime timezone inference.
 *
 * Mount once in app chrome so formatDate/formatDatetime can resolve
 * ``From profile location`` without each page passing contact location.
 *
 * @returns null (side-effect only).
 */
export function ProfileLocationCacheSync() {
  const { data } = useQuery({
    queryKey: ["profile"],
    queryFn: profileApi.get,
    staleTime: 60_000,
    retry: false,
  });

  useEffect(() => {
    writeProfileLocationCache(data?.contact_info?.location ?? null);
  }, [data?.contact_info?.location]);

  return null;
}
